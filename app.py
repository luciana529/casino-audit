import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import json
import base64
import os
import altair as alt
from pathlib import Path
from urllib.parse import urlparse

st.set_page_config(
    page_title="Auditoría Interna - Casino Systems",
    page_icon="🎲",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1a1c23; padding: 15px; border-radius: 8px; border-left: 4px solid #00e676; }
    .stButton>button { width: 100%; background-color: #2979ff; color: white; border-radius: 6px; font-weight: bold; }
    .stButton>button:hover { background-color: #5393ff; }
    </style>
""", unsafe_allow_html=True)

DEFAULT_API_URL = "https://casino-audit-production.up.railway.app/api/v1"
API_URL = os.getenv("API_URL", DEFAULT_API_URL).rstrip("/")
BASE_DIR = Path(__file__).resolve().parent

def cargar_planilla(usuario_id=None, usuario_nombre="Usuario", usuario_rol="empleado", solo_lectura=False, watch_user_id=None):
    index_path = BASE_DIR / "index.html"
    tracker_path = BASE_DIR / "tracker.js"
    if not index_path.exists() or not tracker_path.exists():
        return None
    html_content = index_path.read_text(encoding="utf-8")
    tracker_content = tracker_path.read_text(encoding="utf-8")
    api = urlparse(API_URL)
    api_host = api.netloc or "127.0.0.1:8000"
    configuracion = (
        f"window.API_BASE_URL = {json.dumps(API_URL)}; "
        f"window.API_HOST = {json.dumps(api_host)}; "
        f"window.API_TOKEN = {json.dumps(st.session_state.get('api_token'))}; "
        f"window.CASINO_USER_ID = {json.dumps(usuario_id)}; "
        f"window.CASINO_USER_NAME = {json.dumps(usuario_nombre)}; "
        f"window.CASINO_USER_ROLE = {json.dumps(usuario_rol)}; "
        f"window.PLANILLA_READONLY = {json.dumps(solo_lectura)};\n"
        f"window.WATCH_USER_ID = {json.dumps(watch_user_id)};\n"
    )
    return html_content.replace(
        '<script src="tracker.js"></script>',
        f"<script>{configuracion}{tracker_content}</script>"
    )

def presencia_admin(user):
    api = urlparse(API_URL)
    ws_scheme = "wss" if api.scheme == "https" else "ws"
    ws_url = f"{ws_scheme}://{api.netloc}/ws/live"
    presence_script = f"""
    <script>
    const ws = new WebSocket({json.dumps(ws_url + '?token=' + st.session_state.get('api_token', ''))});
    ws.onopen = () => ws.send(JSON.stringify({{
        type: 'presence', usuario_id: {json.dumps(user['id'])},
        nombre: {json.dumps(user['nombre'])}, rol: 'admin'
    }}));
    setInterval(() => {{
        if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({{
            type: 'presence', usuario_id: {json.dumps(user['id'])},
            nombre: {json.dumps(user['nombre'])}, rol: 'admin'
        }}));
    }}, 20000);
    </script>
    """
    components.html(presence_script, height=1)

@st.fragment(run_every="5s")
def mostrar_usuarios_conectados():
    try:
        respuesta = requests.get(f"{API_URL}/presencia", headers=api_headers(), timeout=5)
        if respuesta.status_code == 200:
            conectados = respuesta.json()
            st.caption(f"🟢 Usuarios conectados ahora: {len(conectados)}")
            if conectados:
                st.dataframe(
                    pd.DataFrame([
                        {"Usuario": item.get("nombre", "Usuario"), "Rol": "Administrador" if item.get("rol") == "admin" else "Empleado"}
                        for item in conectados
                    ]),
                    hide_index=True,
                    use_container_width=True
                )
    except requests.RequestException:
        st.caption("Estado de conexión no disponible.")

@st.fragment(run_every="5s")
def mostrar_dashboard():
    st.subheader("Métricas y Auditoría General")
    try:
        res = requests.get(f"{API_URL}/registros", headers=api_headers(), timeout=10)
        if res.status_code == 200:
            registros = res.json()
            df = pd.DataFrame(registros)
            total_cierres = len(df)
            total_recaudado = pd.to_numeric(df["total_caja"], errors="coerce").fillna(0).sum() if not df.empty else 0

            m1, m2 = st.columns(2)
            m1.metric("Total Cierres", total_cierres)
            m2.metric("Total Recaudado", f"${total_recaudado:,.2f}")

            if registros:
                st.markdown("---")
                st.subheader("Registro Global de Auditoría")
                st.dataframe(
                    df[["id", "nombre_usuario", "operador", "fecha", "hora", "total_caja", "timestamp_servidor"]],
                    use_container_width=True
                )
            else:
                st.info("No hay cierres registrados todavía.")
        else:
            st.error(f"La API respondió con HTTP {res.status_code}.")
    except requests.RequestException as error:
        st.error(f"No se pudo conectar con la API: {error}")

def mostrar_control_cierres():
    st.subheader("Control de cierres")
    res = requests.get(f"{API_URL}/registros", headers=api_headers(), timeout=10)
    if res.status_code != 200:
        st.error(f"No se pudieron cargar los cierres. HTTP {res.status_code}.")
        return

    cierres = res.json()
    if not cierres:
        st.info("No hay cierres registrados todavía.")
        return

    filas = pd.DataFrame(cierres)
    columnas = [
        columna for columna in [
            "id", "nombre_usuario", "operador", "fecha", "hora",
            "total_caja", "timestamp_servidor"
        ] if columna in filas.columns
    ]
    st.dataframe(filas[columnas], hide_index=True, use_container_width=True)

    st.markdown("### Planillas guardadas")
    for cierre in cierres:
        cierre_id = cierre.get("id")
        datos = cierre.get("datos_json", {})
        if isinstance(datos, str):
            try:
                datos = json.loads(datos)
            except json.JSONDecodeError:
                datos = {}

        with st.expander(
            f"Cierre #{cierre_id} | {cierre.get('nombre_usuario', cierre.get('operador', 'Sin operador'))} | {cierre.get('fecha', '')}"
        ):
            imagen = datos.get("imagen_planilla") if isinstance(datos, dict) else None
            if imagen and imagen.startswith("data:image/"):
                try:
                    _, contenido = imagen.split(",", 1)
                    imagen_bytes = base64.b64decode(contenido, validate=True)
                    if st.button("🖼️ Ver planilla guardada", key=f"ver_imagen_{cierre_id}"):
                        st.image(imagen_bytes, caption=f"Planilla del cierre #{cierre_id}", use_container_width=True)
                    st.download_button(
                        "Descargar imagen",
                        data=imagen_bytes,
                        file_name=f"planilla_cierre_{cierre_id}.jpg",
                        mime="image/jpeg",
                        key=f"descargar_imagen_{cierre_id}"
                    )
                except (ValueError, base64.binascii.Error):
                    st.warning("La imagen de este cierre está dañada o incompleta.")
            else:
                st.info("Este cierre no tiene una imagen guardada.")

if "user" not in st.session_state:
    st.session_state.user = None
if "api_token" not in st.session_state:
    st.session_state.api_token = None

def api_headers():
    return {"Authorization": f"Bearer {st.session_state.api_token}"} if st.session_state.api_token else {}

def login(username, password):
    try:
        res = requests.post(f"{API_URL}/login", json={"username": username, "password": password})
        if res.status_code == 200:
            response = res.json()
            st.session_state.user = response["user"]
            st.session_state.api_token = response["token"]
            st.rerun()
        else:
            st.error("Credenciales incorrectas.")
    except Exception as e:
        st.error(f"Error conectando a la API: {e}")

def logout():
    st.session_state.user = None
    st.session_state.api_token = None
    st.rerun()

# --- LOGIN ---
if not st.session_state.user:
    st.title("🎲 Sistema de Auditoría de Casino")
    st.subheader("Acceso al Portal")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            user_input = st.text_input("Usuario")
            pass_input = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Iniciar Sesión"):
                login(user_input, pass_input)
    st.stop()

user = st.session_state.user

# --- PRIMER INGRESO ---
if user.get("requiere_cambio_pass"):
    st.warning("⚠️ Primer Ingreso Detectado: Debes cambiar tu usuario y clave.")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("form_cambio_pass"):
            nuevo_user = st.text_input("Nuevo Usuario", value=user["username"])
            nueva_pass = st.text_input("Nueva Contraseña", type="password")
            confirm_pass = st.text_input("Confirmar Contraseña", type="password")
            if st.form_submit_button("Guardar Cambios"):
                if nueva_pass == confirm_pass and nueva_pass:
                    res = requests.post(f"{API_URL}/cambiar-credenciales", headers=api_headers(), json={"user_id": user["id"], "nuevo_username": nuevo_user, "nueva_password": nueva_pass})
                    if res.status_code == 200:
                        response = res.json()
                        st.session_state.user = response["user"]
                        st.session_state.api_token = response["token"]
                        st.rerun()
    st.stop()

# --- SIDEBAR GLOBAL ---
st.sidebar.title(f"👤 {user['nombre']}")
st.sidebar.caption(f"Rol: **{user['rol'].upper()}** | Usuario: `{user['username']}`")
if st.sidebar.button("🚪 Cerrar Sesión"):
    logout()
st.sidebar.markdown("---")

# --- VISTA EMPLEADO ---
if user["rol"] == "empleado":
    encabezado, accion = st.columns([5, 1])
    with encabezado:
        st.title(f"📄 Caja del Operador: {user['nombre']}")
    with accion:
        if st.button("🚪 Cerrar sesión", key="employee_logout_top", use_container_width=True):
            logout()
    html_content = cargar_planilla(user["id"], user["nombre"], user["rol"])
    if html_content:
        components.html(html_content, height=850, scrolling=True)
    else:
        st.error("No se encontraron index.html y tracker.js junto a app.py.")

# --- VISTA ADMINISTRADOR ---
elif user["rol"] == "admin":
    encabezado, accion = st.columns([5, 1])
    with encabezado:
        st.title("🛡️ Dashboard de Auditoría y Supervisión")
    with accion:
        if st.button("🚪 Cerrar sesión", key="admin_logout_top", use_container_width=True):
            logout()

    acceso_dashboard, acceso_supervision, acceso_crud, acceso_cierres = st.columns(4)
    with acceso_dashboard:
        if st.button("📊 Dashboard", use_container_width=True, key="admin_dashboard_main"):
            st.session_state.admin_section = "dashboard"
            st.rerun()
    with acceso_supervision:
        if st.button("📡 Supervisión en Vivo", use_container_width=True, key="admin_live_main"):
            st.session_state.admin_section = "live"
            st.rerun()
    with acceso_crud:
        if st.button("⚙️ CRUD de Empleados", use_container_width=True, key="admin_crud_main"):
            st.session_state.admin_section = "crud"
            st.rerun()
    with acceso_cierres:
        if st.button("📋 Control de Cierres", use_container_width=True, key="admin_cierres_main"):
            st.session_state.admin_section = "cierres"
            st.rerun()

    if "admin_section" not in st.session_state:
        st.session_state.admin_section = "dashboard"

    st.sidebar.subheader("Navegación")
    if st.sidebar.button("📊 Dashboard", use_container_width=True, key="admin_dashboard"):
        st.session_state.admin_section = "dashboard"
        st.rerun()
    if st.sidebar.button("📡 Supervisión en Vivo", use_container_width=True, key="admin_live"):
        st.session_state.admin_section = "live"
        st.rerun()
    if st.sidebar.button("⚙️ CRUD de Empleados", use_container_width=True, key="admin_crud"):
        st.session_state.admin_section = "crud"
        st.rerun()
    if st.sidebar.button("📋 Control de Cierres", use_container_width=True, key="admin_cierres"):
        st.session_state.admin_section = "cierres"
        st.rerun()

    menu = st.session_state.admin_section
    presencia_admin(user)
    mostrar_usuarios_conectados()
    
    # 1. MONITOREO EN TIEMPO REAL POR EMPLEADO
    if menu == "live":
        st.subheader("Supervisión en Vivo de Planilla")
        res_u = requests.get(f"{API_URL}/usuarios", headers=api_headers())
        if res_u.status_code == 200:
            empleados = [u for u in res_u.json() if u["rol"] == "empleado"]
            if empleados:
                col_lista, col_visor = st.columns([1, 3])
                with col_lista:
                    selected_emp = st.radio(
                        "Selecciona un empleado:",
                        empleados,
                        format_func=lambda empleado: empleado["username"]
                    )
                
                with col_visor:
                    st.markdown(f"### Planilla en vivo: **{selected_emp['nombre']}**")
                    html_content = cargar_planilla(
                        user["id"], user["nombre"], user["rol"],
                        solo_lectura=True, watch_user_id=selected_emp["id"]
                    )
                    if html_content:
                        components.html(html_content, height=800, scrolling=True)
                    else:
                        st.error("No se encontraron index.html y tracker.js junto a app.py.")
            else:
                st.info("No hay empleados registrados.")

    # 2. MÉTRICAS CONSOLIDADAS
    elif menu == "dashboard":
        mostrar_dashboard()

    # 3. CONTROL Y CONSULTA DE CIERRES
    elif menu == "cierres":
        mostrar_control_cierres()

    # 4. GESTIÓN COMPLETA DE EMPLEADOS (CRUD)
    elif menu == "crud":
        st.subheader("Administración de Personal")
        if st.session_state.get("crud_message"):
            st.success(st.session_state.pop("crud_message"))
        
        with st.expander("➕ Crear Empleado"):
            with st.form("form_crear"):
                u_user = st.text_input("Usuario")
                u_nom = st.text_input("Nombre Completo")
                u_pass = st.text_input("Contraseña Inicial", type="password")
                if st.form_submit_button("Guardar Empleado"):
                    res = requests.post(f"{API_URL}/usuarios", headers=api_headers(), json={"username": u_user, "nombre": u_nom, "password": u_pass, "rol": "empleado"})
                    if res.status_code == 200:
                        st.session_state.crud_message = f"✅ Empleado **{u_nom}** creado correctamente."
                        st.rerun()
                    else:
                        st.error(res.json().get("detail", "No se pudo crear el usuario."))

        res_u = requests.get(f"{API_URL}/usuarios", headers=api_headers())
        if res_u.status_code == 200:
            lista_u = res_u.json()
            st.dataframe(pd.DataFrame(lista_u)[["id", "username", "nombre", "rol", "requiere_cambio_pass"]], use_container_width=True)
            
            st.markdown("---")
            col_mod, col_eli = st.columns(2)
            
            # Modificar
            with col_mod:
                st.write("### ✏️ Modificar Usuario")
                usuarios_editables = [u for u in lista_u if u["rol"] == "empleado"]
                u_sel = st.selectbox("Seleccionar usuario para editar:", [u["id"] for u in usuarios_editables], format_func=lambda user_id: next(u["nombre"] for u in usuarios_editables if u["id"] == user_id)) if usuarios_editables else None
                if u_sel:
                    curr_u = next(x for x in lista_u if x["id"] == u_sel)
                    mod_nom = st.text_input("Nombre", value=curr_u["nombre"])
                    mod_user = st.text_input("Usuario", value=curr_u["username"])
                    mod_pass = st.text_input("Nueva Clave (opcional)", type="password")
                    if st.button("Actualizar Datos"):
                        res = requests.put(f"{API_URL}/usuarios/{u_sel}", headers=api_headers(), json={"username": mod_user, "nombre": mod_nom, "password": mod_pass if mod_pass else None, "rol": "empleado"})
                        if res.status_code == 200:
                            st.session_state.crud_message = f"✅ Datos de **{mod_nom}** modificados correctamente."
                            st.rerun()
                        else:
                            st.error(res.json().get("detail", "No se pudo modificar el usuario."))
            
            # Eliminar
            with col_eli:
                st.write("### 🗑️ Eliminar Usuario")
                usuarios_eliminables = [u for u in lista_u if u["rol"] == "empleado"]
                u_del = st.selectbox("Seleccionar usuario para eliminar:", [u["id"] for u in usuarios_eliminables], format_func=lambda user_id: next(u["nombre"] for u in usuarios_eliminables if u["id"] == user_id), key="del_sel") if usuarios_eliminables else None
                if u_del:
                    if st.button("🔴 Confirmar Eliminar", type="primary"):
                        res = requests.delete(f"{API_URL}/usuarios/{u_del}", headers=api_headers())
                        if res.status_code == 200:
                            st.session_state.crud_message = "✅ Empleado eliminado correctamente."
                            st.rerun()
                        else:
                            st.error(res.json().get("detail", "No se pudo eliminar el usuario."))