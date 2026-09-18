import streamlit as st
import requests
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# Configuración de la página
st.set_page_config(
    page_title="Auditoría Casino - Panel de Control",
    page_icon="🎰",
    layout="wide"
)

# Auto-refresco automático cada 3000 ms (3 segundos)
# Mantiene la pantalla actualizada en tiempo real sin requerir interacción
st_autorefresh(interval=3000, key="datarefresh")

st.title("🎰 Panel de Control y Auditoría en Tiempo Real")
st.caption("🔴 En Vivo — Monitoreo automático de planillas cargadas por los 21 operadores")

API_URL = "http://127.0.0.1:8000/api/v1/registros"

@st.cache_data(ttl=2)  # Caché ligero de 2 segundos para no saturar memoria
def cargar_datos():
    try:
        response = requests.get(API_URL, timeout=2)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []

datos = cargar_datos()

if not datos:
    st.info("⏳ Esperando cierres de planillas en vivo... El panel se actualiza automáticamente.")
else:
    # Métricas en tiempo real
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Planillas Reportadas", len(datos))
    
    ultimo_registro = datos[-1]
    col2.metric("Última Carga", ultimo_registro.get("operador", "N/A"))
    col3.metric("Último Total en Caja", f"${ultimo_registro.get('total_caja', 0):,.2f}")

    st.markdown("---")
    st.subheader("📋 Historial Inmutable de Cierres (Actualización automática)")

    # Tabla resumen
    resumen = []
    for reg in datos:
        resumen.append({
            "Fecha/Hora Servidor": reg.get("timestamp_servidor", "N/A"),
            "Operador": reg.get("operador"),
            "Fecha Planilla": reg.get("fecha"),
            "Hora Planilla": reg.get("hora"),
            "Total Caja": f"${reg.get('total_caja', 0):,.2f}"
        })
    
    df_resumen = pd.DataFrame(resumen)
    st.dataframe(df_resumen, use_container_width=True)

    # Inspección detallada
    st.subheader("🔍 Inspección Detallada de Planillas")
    for idx, reg in enumerate(reversed(datos)):
        with st.expander(f"Cierre #{len(datos)-idx} - Operador: {reg.get('operador')} ({reg.get('fecha')} {reg.get('hora')})"):
            st.json(reg)