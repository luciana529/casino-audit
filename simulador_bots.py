import asyncio
import httpx
import websockets
import random
import json
import os

BASE_URL = os.getenv("BOT_API_URL", "http://localhost:8000").rstrip("/")
WS_URL = os.getenv("BOT_WS_URL", "ws://localhost:8000/ws/live")
BOT_PASSWORD = os.getenv("BOT_PASSWORD", "12345")
BOT_COUNT = int(os.getenv("BOT_COUNT", "21"))

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
                    
                    # Enviar una actualización compatible con la planilla cada segundo.
                    while True:
                        letra = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
                        await websocket.send(json.dumps({
                            "type": "cell_update",
                            "usuario_id": user_id,
                            "element_id": "campo-0",
                            "value": letra
                        }))
                        print(f"[Bot {username}] Envió: {letra}")
                        
                        # Esperar exactamente 1 segundo antes de la siguiente letra
                        await asyncio.sleep(1.0)

            except (httpx.RequestError, websockets.exceptions.WebSocketException) as e:
                print(f"[Bot {username}] Desconectado. Reconectando en 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"[Bot {username}] Error: {e}. Reconectando en 5s...")
                await asyncio.sleep(5)

async def main():
    print("=" * 50)
    print("INICIANDO SIMULADOR: 21 EMPLEADOS (1 letra por segundo)")
    print("=" * 50)
    
    # Lanza los 21 bots en paralelo
    tareas = [ejecutar_bot(i) for i in range(1, BOT_COUNT + 1)]
    await asyncio.gather(*tareas)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSimulación detenida por el usuario.")