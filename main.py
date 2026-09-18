from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
import psycopg2.extras
import os
import json
from typing import List, Dict, Any

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

# Crear tabla en PostgreSQL si no existe
def init_db():
    if DATABASE_URL:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cierres (
                id SERIAL PRIMARY KEY,
                operador VARCHAR(100),
                fecha VARCHAR(20),
                hora VARCHAR(20),
                total_caja NUMERIC,
                datos_json JSONB,
                timestamp_servidor TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()

init_db()

class CierreCaja(BaseModel):
    operador: str
    fecha: str
    hora: str
    saldos_inicio: Dict[str, float]
    ingresos: List[Dict[str, Any]]
    egresos: List[Dict[str, Any]]
    total_caja: float

@app.post("/api/v1/cierre")
def registrar_cierre(data: CierreCaja):
    if not DATABASE_URL:
        return {"status": "ok", "mensaje": "Modo Local sin BD"}
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO cierres (operador, fecha, hora, total_caja, datos_json)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (data.operador, data.fecha, data.hora, data.total_caja, json.dumps(data.dict()))
    )
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "ok", "mensaje": "Cierre registrado e inmutable en PostgreSQL"}

@app.get("/api/v1/registros")
def obtener_registros():
    if not DATABASE_URL:
        return []
        
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM cierres ORDER BY id ASC;")
    filas = cursor.fetchall()
    cursor.close()
    conn.close()
    return filas