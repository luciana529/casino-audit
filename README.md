🎲 Sistema de Auditoría Interna y Cierre de Caja - Casino Systems


📑 Tabla de Contenidos
Información General del Proyecto

Estado Actual del Proyecto

Requisitos Previos

Guía de Instalación Paso a Paso

Estructura de Directorios y Archivos

Arquitectura del Sistema

Guía de Uso

Configuración de Entornos

Base de Datos

APIs y Endpoints

Autenticación y Autorización

Despliegue

Tecnologías y Stack Completo

Contribución

Testing

Solución de Problemas Comunes

Roadmap o Próximos Pasos

Licencia y Créditos
----------------------------------------------------------------------------------------------------------------------------------------------
📖 Información General del Proyecto
Descripción
El Sistema de Auditoría Interna y Cierre de Caja es una plataforma integral diseñada para la gestión, supervisión y auditoría en tiempo real de los cuadres de caja en operaciones de casino. Integra un backend reactivo en FastAPI con autenticación HMAC, un frontend administrativo interactivo en Streamlit y una planilla interactiva embedded HTML5/JS sincronizada mediante WebSockets en tiempo real.

Propósito
Digitalizar y automatizar el flujo de trabajo operativo de cierres de caja en los turnos del casino, eliminando planillas en papel o archivos desincronizados, garantizando la persistencia inmutable en base de datos PostgreSQL y permitiendo la supervisión en vivo campo por campo por parte del personal de auditoría/administración.

Alcance y Objetivos
Control de accesos estricto: Separación de funciones por rol (Empleado / Administrador).

Flujo interactivo de celdas: Planilla interactiva HTML5 con validaciones automáticas de saldos, ingresos y egresos.

Supervisión en vivo: Retransmisión instantánea vía WebSockets de las celdas editadas por los empleados hacia el panel administrativo.

Auditoría e informes: Visualización de métricas consolidadas, histórico de recaudación por operador e indicadores de rendimiento.

📊 Estado Actual del Proyecto
Estado General: Producción / Completado (100%)

Fase / Módulo	Estado	Porcentaje
Backend REST API (FastAPI)	Completado	100%
Esquema de Base de Datos PostgreSQL	Completado	100%
Seguridad Token HMAC + Control de Roles	Completado	100%
Sincronización WebSockets (wss://)	Completado	100%
Frontend Streamlit (Admin & Dashboard)	Completado	100%
Planilla Embedded HTML5/JS (index.html + tracker.js)	Completado	100%
Despliegue en la Nube (Render Cloud Services)	Completado	100%
🛠️ Requisitos Previos
Python: 3.10.x o superior

PostgreSQL: Versión 15+ (Local o Instancia Cloud/Render)

Navegador Web: Google Chrome, Mozilla Firefox o Microsoft Edge con soporte para WebSockets HTML5.

Herramientas de Cliente SQL (Opcional): DBeaver, pgAdmin o extensión de VSCode para administración de base de datos.

Git: 2.30+ para control de versiones.

🚀 Guía de Instalación Paso a Paso
1. Clonar el Repositorio
Bash
git clone [https://github.com/tu-usuario/casino-audit.git](https://github.com/tu-usuario/casino-audit.git)
cd casino-audit
2. Crear y Activar Entorno Virtual
Bash
# En Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# En Linux / macOS
python3 -m venv venv
source venv/bin/activate
3. Instalar Dependencias
Bash
pip install --upgrade pip
pip install -r requirements.txt
4. Configurar Variables de Entorno Locales
Crea un archivo .env en la raíz del proyecto con la siguiente estructura:

Ini, TOML
# Configuración del Backend API
DATABASE_URL=postgresql://usuario:password@localhost:5432/casino_db
AUTH_SECRET=clave-secreta-desarrollo-local-2026

# Configuración del Frontend Streamlit
API_URL=[http://127.0.0.1:8000/api/v1](http://127.0.0.1:8000/api/v1)
5. Inicializar la Base de Datos
Al arrancar la API por primera vez, el método init_db() creará automáticamente las tablas usuarios y cierres e insertará los usuarios iniciales.

📁 Estructura de Directorios y Archivos
Plaintext
casino-audit/
├── app.py              # Frontend principal en Streamlit (Dashboard & Interfaz Empleado/Admin)
├── main.py             # Backend REST API en FastAPI (Endpoints, Auth HMAC, WebSockets, DB)
├── index.html          # Interfaz interactiva de la planilla de cierre de caja (HTML5)
├── tracker.js          # Lógica cliente JS (Validaciones, conexión WS y envío de formulario)
├── requirements.txt    # Librerías y dependencias de Python requeridas
├── Procfile            # Comando de arranque para despliegue en producción
├── runtime.txt         # Especificación de versión de Python para el servidor de nube
└── .env.example        # Plantilla de variables de entorno de ejemplo
📐 Arquitectura del Sistema
El sistema utiliza una arquitectura de microservicios desacoplada desplegada en contenedores independientes sobre Render Cloud Services.

Plaintext
┌─────────────────────────────────────────────────────────────────┐
│                       STREAMLIT DASHBOARD                       │
│                     (App Web de Usuario / Admin)                │
└────────────────┬────────────────────────────────▲───────────────┘
                 │                                │
      Peticiones REST (HTTP)             Recepción WS Live
                 │                                │
                 ▼                                │
┌─────────────────────────────────────────────────┴───────────────┐
│                         FASTAPI BACKEND                         │
│         (Motor de Negocio, Auth HMAC & ConnectionManager)       │
└────────────────┬────────────────────────────────▲───────────────┘
                 │                                │
        Consultas SQL (psycopg2)         Sincronización
                 │                                │
                 ▼                                │
┌─────────────────────────────────────────────────┴───────────────┐
│                       POSTGRESQL DATABASE                       │
│                   (Tablas: usuarios, cierres)                   │
└─────────────────────────────────────────────────────────────────┘
⚙️ Guía de Uso
Ejecutar Backend API en Desarrollo
Bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
Documentación interactiva Swagger UI disponible en: http://127.0.0.1:8000/docs

Ejecutar Frontend Dashboard en Desarrollo
Bash
streamlit run app.py
Acceso a la interfaz web en: http://localhost:8501

🌐 Configuración de Entornos
Variable	Entorno Desarrollo	Entorno Producción (Render)
DATABASE_URL	postgresql://user:pass@localhost:5432/db	postgresql://casino_db_user:...@dpg-...postgres.render.com/casino_db
AUTH_SECRET	local-dev-secret	super-clave-secreta-casino-audit-2026-x9z
API_URL	http://127.0.0.1:8000/api/v1	https://casino-audit-api.onrender.com/api/v1
🗄️ Base de Datos
Esquema Relacional (PostgreSQL)
Tabla usuarios
SQL
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    rol VARCHAR(20) NOT NULL DEFAULT 'empleado',
    requiere_cambio_pass BOOLEAN DEFAULT TRUE
);
Tabla cierres
SQL
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
Limpieza de Datos de Prueba (Mantenimiento SQL)
Para reiniciar los registros de caja sin afectar las cuentas de usuarios:

SQL
TRUNCATE TABLE cierres RESTART IDENTITY;
🔌 APIs y Endpoints
Autenticación & Usuarios
POST /api/v1/login

Payload: {"username": "admin", "password": "..."}

Respuesta: Objeto usuario + Token HMAC Bearer.

POST /api/v1/cambiar-credenciales

Header: Authorization: Bearer <token>

Payload: {"user_id": 1, "nuevo_username": "...", "nueva_password": "..."}

GET /api/v1/usuarios (Solo Admin)

Header: Authorization: Bearer <token>

Respuesta: Lista global de usuarios.

POST /api/v1/usuarios (Solo Admin)

Header: Authorization: Bearer <token>

Payload: {"username": "...", "password": "...", "nombre": "...", "rol": "empleado"}

Cierres & Auditoría
POST /api/v1/cierre

Header: Authorization: Bearer <token>

Payload: JSON completo del estado del turno y montos.

GET /api/v1/registros

Header: Authorization: Bearer <token>

Respuesta: Histórico de cierres (filtrado por usuario para empleados, global para admins).

Tiempo Real (WebSockets)
WS /ws/live?token=<api_token>

Requerido para la emisión y recepción de eventos de celda (cell_update) y estado de presencia.

🔐 Autenticación y Autorización
El sistema implementa una arquitectura Stateless basada en Tokens HMAC-SHA256:

Generación de Token: Al autenticarse, se firma digitalmente un payload en formato Base64 con el AUTH_SECRET.

Validación de Expiración: Los tokens poseen un TTL (Time To Live) por defecto de 8 horas.

Flujo de Primer Ingreso: Si requiere_cambio_pass es True, el sistema redirige forzosamente al usuario al formulario de cambio de credenciales iniciales.

Protección de Envoltorio: Los endpoints administrativos están protegidos por la dependencia admin_user.

☁️ Despliegue en Producción (Render Cloud Services)
Servicio 1: API REST + WebSockets
Tipo: Web Service (Python 3)

Build Command: pip install -r requirements.txt

Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT

Variables de Entorno: DATABASE_URL, AUTH_SECRET

Servicio 2: Frontend Dashboard
Tipo: Web Service (Python 3)

Build Command: pip install -r requirements.txt

Start Command: streamlit run app.py --server.port $PORT

Variables de Entorno: API_URL, AUTH_SECRET

Servicio 3: Base de Datos Relacional
Tipo: Render PostgreSQL Instance

💻 Tecnologías y Stack Completo
Backend: Python 3.10, FastAPI, Uvicorn, Pydantic, Psycopg2.

Frontend: Streamlit, Pandas, Altair (Visualizaciones gráficos de barra), HTML5, CSS3, JavaScript ES6.

Base de Datos: PostgreSQL con soporte nativo de tipo JSONB.

Protocolos: HTTP REST / WebSockets (wss://).

🤝 Contribución
Haz un Fork del repositorio.

Crea una rama de funcionalidad (git checkout -b feature/nueva-funcionalidad).

Realiza los commits siguiendo el estándar convencional (git commit -m "feat: agrega nueva funcionalidad").

Haz Push a la rama (git push origin feature/nueva-funcionalidad).

Abre un Pull Request para revisión.

🧪 Testing
Pruebas de Endpoints con Swagger
Puedes validar la respuesta de todos los endpoints navegando directamente a https://casino-audit-api.onrender.com/docs.

Verificación Manual de Sincronización
Abre una sesión como Empleado en una ventana de incógnito.

Abre una sesión como Administrador en la ventana principal e ingresa a Supervisión en Vivo.

Edita cualquier casilla de la planilla y comprueba la actualización simultánea en la pantalla del supervisor.

❓ Solución de Problemas Comunes
Credenciales incorrectas al iniciar sesión:

Verifica en DBeaver que no existan espacios en blanco en la columna username o password.

Asegúrate de que la variable API_URL en Streamlit apunte a la ruta con /api/v1.

HTTP 500 al cargar el Dashboard:

Asegúrate de que la columna usuario_id exista en la tabla cierres de PostgreSQL.

Ejecuta TRUNCATE TABLE cierres RESTART IDENTITY; para eliminar datos nulos de pruebas previas.

Los cambios de la planilla no se reflejan en vivo:

Revisa la consola del navegador (F12) para comprobar que el WebSocket esté conectado en puerto seguro wss:// con el token adjunto.

🔮 Roadmap o Próximos Pasos
[ ] Exportación directa de cierres a formato PDF / Excel firmado.

[ ] Implementación de encriptación Hash Bcrypt para contraseñas.

[ ] Notificaciones automáticas por Telegram/Email al detectar un descuadre crítico en caja.

📄 Licencia y Créditos
Este proyecto se distribuye bajo la Licencia MIT.

Desarrollado por: Luciana Ramirez Systems

