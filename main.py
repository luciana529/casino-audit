from fastapi import FastAPI, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
import psycopg2.extras
import os
import json
import base64
import hashlib
import hmac
import time
from typing import List, Dict, Any, Optional

app = FastAPI(title="Casino Audit API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL")
AUTH_SECRET = os.getenv("AUTH_SECRET", "local-development-secret-change-before-render")
TOKEN_TTL_SECONDS = 8 * 60 * 60

USUARIOS_LOCALES = [
    {"id": 1, "username": "admin", "password": "admin123", "nombre": "Administrador General", "rol": "admin", "requiere_cambio_pass": False},
    {"id": 2, "username": "empleado1", "password": "1234", "nombre": "Empleado 1", "rol": "empleado", "requiere_cambio_pass": True}
]

CIERRES_LOCALES = []
ESTADOS_PLANILLA = {}

def get_db():
    url = DATABASE_URL
    if not url:
        raise RuntimeError("DATABASE_URL no está configurada")

    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgres://", 1)

    if "railway.internal" in url:
        return psycopg2.connect(url)
    return psycopg2.connect(url, sslmode="require")

def init_db():
    if DATABASE_URL:
        try:
            conn = get_db()
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password VARCHAR(100) NOT NULL,
                    nombre VARCHAR(100) NOT NULL,
                    rol VARCHAR(20) NOT NULL DEFAULT 'empleado',
                    requiere_cambio_pass BOOLEAN DEFAULT TRUE
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cierres (
                    id SERIAL PRIMARY KEY,
                    usuario_id INT REFERENCES usuarios(id),
                    operador VARCHAR(100),
                    fecha VARCHAR(20),
                    hora VARCHAR(20),
                    total_caja NUMERIC,
                    datos_json JSONB,
                    timestamp_servidor TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cursor.execute("SELECT COUNT(*) FROM usuarios;")
            cantidad_usuarios = cursor.fetchone()[0]

            # Solo crear las cuentas iniciales cuando la tabla todavía está vacía.
            # Los cambios posteriores de username, password o rol quedan preservados.
            if cantidad_usuarios == 0:
                cursor.execute("""
                    INSERT INTO usuarios (username, password, nombre, rol, requiere_cambio_pass)
                    VALUES
                        ('admin', 'admin123', 'Administrador General', 'admin', FALSE),
                        ('empleado1', '1234', 'Empleado 1', 'empleado', TRUE);
                """)

            conn.commit()
            cursor.close()
            conn.close()
            print("--- BASE DE DATOS INICIALIZADA CON ÉXITO ---")
        except Exception as error:
            print(f"--- ERROR AL INICIALIZAR LA BASE DE DATOS: {error} ---")

init_db()

def create_token(user: Dict[str, Any]) -> str:
    payload = {
        "id": user["id"],
        "username": user["username"],
        "rol": user["rol"],
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(AUTH_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"

def verify_token(token: str) -> Dict[str, Any]:
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(AUTH_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError
        return payload
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, base64.binascii.Error):
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada")

def current_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Autenticación requerida")
    return verify_token(authorization[7:].strip())

def admin_user(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    if user.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Se requieren permisos de administrador")
    return user

# --- GESTOR DE CONEXIONES WEBSOCKET EN TIEMPO REAL ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_users: Dict[WebSocket, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.connection_users.pop(websocket, None)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            if self.connection_users.get(connection, {}).get("rol") != "admin":
                continue
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return
    try:
        authenticated_user = verify_token(token)
    except HTTPException:
        await websocket.close(code=1008)
        return
        
    await manager.connect(websocket)
    manager.connection_users[websocket] = {
        "usuario_id": authenticated_user["id"],
        "nombre": authenticated_user["username"],
        "rol": authenticated_user["rol"]
    }
    
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            if payload.get("type") == "presence":
                continue
            else:
                payload["usuario_id"] = authenticated_user["id"]
                if payload.get("element_id") and payload.get("value") is not None:
                    ESTADOS_PLANILLA.setdefault(authenticated_user["id"], {})[payload["element_id"]] = payload["value"]
                await manager.broadcast(json.dumps(payload))
    except (WebSocketDisconnect, json.JSONDecodeError):
        manager.disconnect(websocket)

# Models
class LoginRequest(BaseModel):
    username: str
    password: str

class CambiarCredencialesRequest(BaseModel):
    user_id: int
    nuevo_username: str
    nueva_password: str

class UserCreate(BaseModel):
    username: str
    password: str
    nombre: str
    rol: str = "empleado"

class UserUpdate(BaseModel):
    username: str
    nombre: str
    password: Optional[str] = None
    rol: str = "empleado"

class CierreCaja(BaseModel):
    usuario_id: Optional[int] = None
    operador: str
    fecha: str
    hora: str
    hora_inicio: Optional[str] = None
    hora_cierre: Optional[str] = None
    saldos_inicio: Dict[str, float]
    ingresos: List[Dict[str, Any]]
    egresos: List[Dict[str, Any]]
    total_caja: float
    estado_planilla: Dict[str, str] = {}

# --- ENDPOINTS USUARIOS (CRUD) ---
@app.post("/api/v1/login")
def login(data: LoginRequest):
    user_clean = data.username.strip()
    pass_clean = data.password.strip()

    if not DATABASE_URL:
        for u in USUARIOS_LOCALES:
            if u["username"] == user_clean and u["password"] == pass_clean:
                user_data = u.copy()
                del user_data["password"]
                return {"status": "ok", "user": user_data, "token": create_token(user_data)}
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        "SELECT id, username, nombre, rol, requiere_cambio_pass FROM usuarios WHERE TRIM(username) = %s AND TRIM(password) = %s;",
        (user_clean, pass_clean)
    )
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    user_data = dict(user)
    return {"status": "ok", "user": user_data, "token": create_token(user_data)}

@app.post("/api/v1/cambiar-credenciales")
def cambiar_credenciales(data: CambiarCredencialesRequest, user: Dict[str, Any] = Depends(current_user)):
    if data.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="No puedes cambiar las credenciales de otro usuario")
    if not DATABASE_URL:
        for u in USUARIOS_LOCALES:
            if u["id"] == data.user_id:
                u["username"] = data.nuevo_username.strip()
                u["password"] = data.nueva_password.strip()
                u["requiere_cambio_pass"] = False
                user_data = u.copy()
                del user_data["password"]
                return {"status": "ok", "mensaje": "Credenciales actualizadas", "user": user_data, "token": create_token(user_data)}
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute(
            "UPDATE usuarios SET username = %s, password = %s, requiere_cambio_pass = FALSE WHERE id = %s RETURNING id, username, nombre, rol, requiere_cambio_pass;",
            (data.nuevo_username.strip(), data.nueva_password.strip(), data.user_id)
        )
        updated_user = cursor.fetchone()
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="El usuario ya existe")
    finally:
        cursor.close()
        conn.close()
        
    user_data = dict(updated_user)
    return {"status": "ok", "user": user_data, "token": create_token(user_data)}

@app.get("/api/v1/usuarios")
def obtener_usuarios(_: Dict[str, Any] = Depends(admin_user)):
    if not DATABASE_URL:
        return [{"id": u["id"], "username": u["username"], "nombre": u["nombre"], "rol": u["rol"], "requiere_cambio_pass": u.get("requiere_cambio_pass", False)} for u in USUARIOS_LOCALES]

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT id, username, nombre, rol, requiere_cambio_pass FROM usuarios ORDER BY id ASC;")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return users

@app.post("/api/v1/usuarios")
def crear_usuario(data: UserCreate, _: Dict[str, Any] = Depends(admin_user)):
    if data.rol != "empleado":
        raise HTTPException(status_code=403, detail="Los administradores se cargan manualmente")
    if not DATABASE_URL:
        nuevo_id = len(USUARIOS_LOCALES) + 1
        nuevo_u = {"id": nuevo_id, "username": data.username.strip(), "password": data.password.strip(), "nombre": data.nombre, "rol": data.rol, "requiere_cambio_pass": True}
        USUARIOS_LOCALES.append(nuevo_u)
        return {"status": "ok", "mensaje": "Usuario creado"}

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO usuarios (username, password, nombre, rol, requiere_cambio_pass) VALUES (%s, %s, %s, %s, TRUE);",
            (data.username.strip(), data.password.strip(), data.nombre, data.rol)
        )
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe")
    finally:
        cursor.close()
        conn.close()
    return {"status": "ok", "mensaje": "Usuario creado"}

@app.put("/api/v1/usuarios/{user_id}")
def actualizar_usuario(user_id: int, data: UserUpdate, _: Dict[str, Any] = Depends(admin_user)):
    if data.rol != "empleado":
        raise HTTPException(status_code=403, detail="Los administradores son fijos")
    if not DATABASE_URL:
        for u in USUARIOS_LOCALES:
            if u["id"] == user_id:
                if u["rol"] != "empleado":
                    raise HTTPException(status_code=403, detail="Los administradores son fijos")
                u["username"] = data.username.strip()
                u["nombre"] = data.nombre
                u["rol"] = data.rol
                if data.password:
                    u["password"] = data.password.strip()
                return {"status": "ok", "mensaje": "Usuario modificado"}
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT rol FROM usuarios WHERE id = %s;", (user_id,))
        target = cursor.fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if target[0] != "empleado":
            raise HTTPException(status_code=403, detail="Los administradores son fijos")
        if data.password:
            cursor.execute("UPDATE usuarios SET username = %s, nombre = %s, rol = %s, password = %s WHERE id = %s;", (data.username.strip(), data.nombre, data.rol, data.password.strip(), user_id))
        else:
            cursor.execute("UPDATE usuarios SET username = %s, nombre = %s, rol = %s WHERE id = %s;", (data.username.strip(), data.nombre, data.rol, user_id))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return {"status": "ok", "mensaje": "Usuario modificado"}

@app.delete("/api/v1/usuarios/{user_id}")
def eliminar_usuario(user_id: int, admin: Dict[str, Any] = Depends(admin_user)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta")
    if not DATABASE_URL:
        global USUARIOS_LOCALES
        target = next((u for u in USUARIOS_LOCALES if u["id"] == user_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if target["rol"] != "empleado":
            raise HTTPException(status_code=403, detail="Los administradores son fijos")
        USUARIOS_LOCALES = [u for u in USUARIOS_LOCALES if u["id"] != user_id]
        return {"status": "ok", "mensaje": "Usuario eliminado"}

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT rol FROM usuarios WHERE id = %s;", (user_id,))
    target = cursor.fetchone()
    if not target:
        cursor.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if target[0] != "empleado":
        cursor.close()
        raise HTTPException(status_code=403, detail="Los administradores son fijos")
    cursor.execute("DELETE FROM usuarios WHERE id = %s;", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "ok", "mensaje": "Usuario eliminado"}

# --- ENDPOINTS CIERRES ---
@app.post("/api/v1/cierre")
async def registrar_cierre(data: CierreCaja, user: Dict[str, Any] = Depends(current_user)):
    if user["rol"] == "empleado":
        data.usuario_id = user["id"]
        data.operador = user["username"]
    ESTADOS_PLANILLA[data.usuario_id or user["id"]] = dict(data.estado_planilla)
    if not DATABASE_URL:
        nuevo_id = len(CIERRES_LOCALES) + 1
        registro = {
            "id": nuevo_id,
            "usuario_id": data.usuario_id,
            "operador": data.operador,
            "nombre_usuario": data.operador,
            "fecha": data.fecha,
            "hora": data.hora,
            "hora_inicio": data.hora_inicio,
            "hora_cierre": data.hora_cierre,
            "total_caja": data.total_caja,
            "datos_json": json.dumps(data.dict()),
            "timestamp_servidor": "2026-03-27 10:00:00"
        }
        CIERRES_LOCALES.append(registro)
        await manager.broadcast(json.dumps({
            "type": "closure_saved",
            "usuario_id": user["id"],
            "state": data.estado_planilla
        }))
        return {"status": "ok", "mensaje": "Cierre registrado"}
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO cierres (usuario_id, operador, fecha, hora, total_caja, datos_json) VALUES (%s, %s, %s, %s, %s, %s)",
        (data.usuario_id, data.operador, data.fecha, data.hora, data.total_caja, json.dumps(data.dict()))
    )
    conn.commit()
    cursor.close()
    conn.close()
    await manager.broadcast(json.dumps({
        "type": "closure_saved",
        "usuario_id": user["id"],
        "state": data.estado_planilla
    }))
    return {"status": "ok", "mensaje": "Cierre registrado"}

@app.get("/api/v1/registros")
def obtener_registros(user: Dict[str, Any] = Depends(current_user)):
    if not DATABASE_URL:
        if user["rol"] == "admin":
            return CIERRES_LOCALES
        return [registro for registro in CIERRES_LOCALES if registro.get("usuario_id") == user["id"]]
        
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if user["rol"] == "admin":
        cursor.execute("""
            SELECT c.id, c.usuario_id, c.operador, c.fecha, c.hora, c.total_caja, c.datos_json, c.timestamp_servidor::text as timestamp_servidor, u.username, u.nombre as nombre_usuario
            FROM cierres c
            LEFT JOIN usuarios u ON c.usuario_id = u.id
            ORDER BY c.id DESC;
        """)
    else:
        cursor.execute("""
            SELECT c.id, c.usuario_id, c.operador, c.fecha, c.hora, c.total_caja, c.datos_json, c.timestamp_servidor::text as timestamp_servidor, u.username, u.nombre as nombre_usuario
            FROM cierres c
            LEFT JOIN usuarios u ON c.usuario_id = u.id
            WHERE c.usuario_id = %s
            ORDER BY c.id DESC;
        """, (user["id"],))
    filas = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(f) for f in filas]

@app.get("/api/v1/presencia")
def obtener_presencia(_: Dict[str, Any] = Depends(admin_user)):
    usuarios = {}
    for usuario in manager.connection_users.values():
        clave = usuario.get("usuario_id") or f"anonimo-{id(usuario)}"
        usuarios[str(clave)] = usuario
    return list(usuarios.values())

@app.get("/api/v1/planilla/{user_id}/estado")
def obtener_estado_planilla(user_id: int, _: Dict[str, Any] = Depends(admin_user)):
    return ESTADOS_PLANILLA.get(user_id, {})