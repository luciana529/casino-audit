import asyncio
import httpx
import websockets
import random
import json
import os
from datetime import datetime

BASE_URL = os.getenv("BOT_API_URL", "https://casino-audit-production.up.railway.app").rstrip("/")
WS_URL = os.getenv("BOT_WS_URL", "wss://casino-audit-production.up.railway.app/ws/live")
BOT_PASSWORD = os.getenv("BOT_PASSWORD", "12345")
BOT_COUNT = int(os.getenv("BOT_COUNT", "21"))
PAUSA_ENTRE_CELDAS = float(os.getenv("BOT_PAUSA_ENTRE_CELDAS", "0.2"))
PAUSA_ENTRE_CIERRES = float(os.getenv("BOT_PAUSA_ENTRE_CIERRES", "60"))


def datos_primera_fila(user_id):
    """Devuelve los nueve valores de la primera fila de la tabla principal."""
    return {
        "campo-4": f"usuario_{user_id}",
        "campo-5": str(random.randint(1000, 5000)),
        "campo-6": str(random.randint(0, 250)),
        "campo-7": str(random.randint(0, 100)),
        "campo-8": f"promo_{user_id}",
        "campo-9": str(random.randint(0, 500)),
        "campo-10": f"egreso_{user_id}",
        "campo-11": str(random.randint(1, 100)),
        "campo-12": str(random.randint(0, 250)),
    }


async def cargar_primera_fila(websocket, user_id):
    valores = datos_primera_fila(user_id)
    for element_id, value in valores.items():
        await websocket.send(json.dumps({
            "type": "cell_update",
            "usuario_id": user_id,
            "element_id": element_id,
            "value": value,
        }))
        print(f"[Bot empleado{user_id}] Cargó {element_id}: {value}")
        await asyncio.sleep(PAUSA_ENTRE_CELDAS)
    return valores


async def guardar_cierre(client, token, user_id, valores):
    ahora = datetime.now()
    payload = {
        "usuario_id": user_id,
        "operador": f"empleado{user_id}",
        "fecha": ahora.strftime("%Y-%m-%d"),
        "hora": ahora.strftime("%H:%M"),
        "hora_inicio": ahora.strftime("%H:%M"),
        "hora_cierre": ahora.strftime("%H:%M"),
        "saldos_inicio": {
            "billetera": 0,
            "celu_apuestas": 0,
            "ganamos": 0,
            "gana_en_casa": 0,
            "bet30": 0,
        },
        "ingresos": [{
            "usuario": valores["campo-4"],
            "monto": float(valores["campo-5"]),
            "descuento": float(valores["campo-6"]),
            "dinamica": float(valores["campo-7"]),
            "fichas_gratis_nombre": valores["campo-8"],
            "fichas_gratis_monto": float(valores["campo-9"]),
        }],
        "egresos": [{
            "usuario": valores["campo-10"],
            "retiro_pct": float(valores["campo-11"]),
            "fr": float(valores["campo-12"]),
        }],
        "total_caja": 0,
        "imagen_planilla": None,
        "estado_planilla": valores,
    }
    response = await client.post(
        f"{BASE_URL}/api/v1/cierre",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    response.raise_for_status()
    print(f"[Bot empleado{user_id}] Guardó el cierre de la primera fila.")

async def ejecutar_bot(user_id):
    username = f"empleado{user_id}"
    password = BOT_PASSWORD
    
    async with httpx.AsyncClient() as client:
        while True:
            try:
                # 1. Login para obtener el token o sesión
                login_res = await client.post(f"{BASE_URL}/api/v1/login", json={
                    "username": username,
                    "password": password
                })
                
                if login_res.status_code != 200:
                    print(f"[Bot {username}] Error de login. Reintentando en 10s...")
                    await asyncio.sleep(10)
                    continue
                
                token = login_res.json().get("token")
                if not token:
                    print(f"[Bot {username}] La API no devolvió token. Reintentando en 10s...")
                    await asyncio.sleep(10)
                    continue

                # 2. Conectarse al WebSocket
                uri = f"{WS_URL}?token={token}"
                
                async with websockets.connect(uri) as websocket:
                    print(f"[Bot {username}] ¡Conectado! Comenzando a enviar datos...")
                    await websocket.send(json.dumps({
                        "type": "presence",
                        "usuario_id": user_id,
                        "nombre": username,
                        "rol": "empleado"
                    }))
                    
                    # Simular la carga de la primera fila y luego Guardar como Imagen.
                    valores = await cargar_primera_fila(websocket, user_id)
                    await asyncio.sleep(PAUSA_ENTRE_CELDAS)
                    await guardar_cierre(client, token, user_id, valores)
                    return

            except (httpx.RequestError, websockets.exceptions.WebSocketException) as e:
                print(f"[Bot {username}] Desconectado. Reconectando en 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"[Bot {username}] Error: {e}. Reconectando en 5s...")
                await asyncio.sleep(5)

async def main():
    print("=" * 50)
    print(f"INICIANDO SIMULADOR: {BOT_COUNT} EMPLEADOS (EN SECUENCIA)")
    print("=" * 50)
    
    while True:
        for user_id in range(1, BOT_COUNT + 1):
            await ejecutar_bot(user_id)
            print(f"[Simulador] Empleado{user_id} terminó. Próximo empleado en {PAUSA_ENTRE_CIERRES:g}s.")
            await asyncio.sleep(PAUSA_ENTRE_CIERRES)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSimulación detenida por el usuario.")