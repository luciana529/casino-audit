from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
import psycopg2.extras
import os
import json
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

USUARIOS_LOCALES = [
    {"id": 1, "username": "admin", "password": "admin123", "nombre": "Administrador General", "rol": "admin", "requiere_cambio_pass": False},
    {"id": 2, "username": "empleado1", "password": "1234", "nombre": "Empleado 1", "rol": "empleado", "requiere_cambio_pass": True}
]

CIERRES_LOCALES = []

def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    if DATABASE_URL:
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
        
        cursor.execute("""
            INSERT INTO usuarios (username, password, nombre, rol, requiere_cambio_pass)
            VALUES ('admin', 'admin123', 'Administrador General', 'admin', FALSE)
            ON CONFLICT (username) DO NOTHING;
        """)
        
        cursor.execute("""
            INSERT INTO usuarios (username, password, nombre, rol, requiere_cambio_pass)
            VALUES ('empleado1', '1234', 'Empleado 1', 'empleado', TRUE)
            ON CONFLICT (username) DO NOTHING;
        """)
        
        conn.commit()
        cursor.close()
        conn.close()

init_db()

# --- GESTOR DE CONEXIONES WEBSOCKET EN TIEMPO REAL ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Retransmitir cambios de la planilla a los administradores en vivo
            await manager.broadcast(data)
    except WebSocketDisconnect:
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

# --- ENDPOINTS USUARIOS (CRUD) ---
@app.post("/api/v1/login")
def login(data: LoginRequest):
    if not DATABASE_URL:
        for u in USUARIOS_LOCALES:
            if u["username"] == data.username and u["password"] == data.password:
                user_data = u.copy()
                del user_data["password"]
                return {"status": "ok", "user": user_data}
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        "SELECT id, username, nombre, rol, requiere_cambio_pass FROM usuarios WHERE username = %s AND password = %s;",
        (data.username, data.password)
    )
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    return {"status": "ok", "user": dict(user)}

@app.post("/api/v1/cambiar-credenciales")
def cambiar_credenciales(data: CambiarCredencialesRequest):
    if not DATABASE_URL:
        for u in USUARIOS_LOCALES:
            if u["id"] == data.user_id:
                u["username"] = data.nuevo_username
                u["password"] = data.nueva_password
                u["requiere_cambio_pass"] = False
                user_data = u.copy()
                del user_data["password"]
                return {"status": "ok", "mensaje": "Credenciales actualizadas", "user": user_data}
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute(
            "UPDATE usuarios SET username = %s, password = %s, requiere_cambio_pass = FALSE WHERE id = %s RETURNING id, username, nombre, rol, requiere_cambio_pass;",
            (data.nuevo_username, data.nueva_password, data.user_id)
        )
        updated_user = cursor.fetchone()
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="El usuario ya existe")
    finally:
        cursor.close()
        conn.close()
        
    return {"status": "ok", "user": dict(updated_user)}

@app.get("/api/v1/usuarios")
def obtener_usuarios():
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
def crear_usuario(data: UserCreate):
    if not DATABASE_URL:
        nuevo_id = len(USUARIOS_LOCALES) + 1
        nuevo_u = {"id": nuevo_id, "username": data.username, "password": data.password, "nombre": data.nombre, "rol": data.rol, "requiere_cambio_pass": True}
        USUARIOS_LOCALES.append(nuevo_u)
        return {"status": "ok", "mensaje": "Usuario creado"}

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO usuarios (username, password, nombre, rol, requiere_cambio_pass) VALUES (%s, %s, %s, %s, TRUE);",
            (data.username, data.password, data.nombre, data.rol)
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
def actualizar_usuario(user_id: int, data: UserUpdate):
    if not DATABASE_URL:
        for u in USUARIOS_LOCALES:
            if u["id"] == user_id:
                u["username"] = data.username
                u["nombre"] = data.nombre
                u["rol"] = data.rol
                if data.password:
                    u["password"] = data.password
                return {"status": "ok", "mensaje": "Usuario modificado"}
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    conn = get_db()
    cursor = conn.cursor()
    try:
        if data.password:
            cursor.execute("UPDATE usuarios SET username = %s, nombre = %s, rol = %s, password = %s WHERE id = %s;", (data.username, data.nombre, data.rol, data.password, user_id))
        else:
            cursor.execute("UPDATE usuarios SET username = %s, nombre = %s, rol = %s WHERE id = %s;", (data.username, data.nombre, data.rol, user_id))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return {"status": "ok", "mensaje": "Usuario modificado"}

@app.delete("/api/v1/usuarios/{user_id}")
def eliminar_usuario(user_id: int):
    if not DATABASE_URL:
        global USUARIOS_LOCALES
        USUARIOS_LOCALES = [u for u in USUARIOS_LOCALES if u["id"] != user_id]
        return {"status": "ok", "mensaje": "Usuario eliminado"}

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM usuarios WHERE id = %s;", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "ok", "mensaje": "Usuario eliminado"}

# --- ENDPOINTS CIERRES ---
@app.post("/api/v1/cierre")
def registrar_cierre(data: CierreCaja):
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
    return {"status": "ok", "mensaje": "Cierre registrado"}

@app.get("/api/v1/registros")
def obtener_registros():
    if not DATABASE_URL:
        return CIERRES_LOCALES
        
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        SELECT c.*, u.username, u.nombre as nombre_usuario 
        FROM cierres c
        LEFT JOIN usuarios u ON c.usuario_id = u.id
        ORDER BY c.id DESC;
    """)
    filas = cursor.fetchall()
    cursor.close()
    conn.close()
    return filas