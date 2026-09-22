import asyncio
import httpx
import websockets
import random

# Configura aquí la URL base de tu backend y la ruta del WebSocket
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws" 

async def ejecutar_bot(user_id):
    username = f"empleado{user_id}"
    password = "12345"
    
    async with httpx.AsyncClient() as client:
        while True:
            try:
                # 1. Login para obtener el token o sesión
                login_res = await client.post(f"{BASE_URL}/api/login", json={
                    "username": username,
                    "password": password
                })
                
                if login_res.status_code != 200:
                    print(f"[Bot {username}] Error de login. Reintentando en 10s...")
                    await asyncio.sleep(10)
                    continue
                
                token = login_res.json().get("access_token")

                # 2. Conectarse al WebSocket
                uri = f"{WS_URL}?token={token}"
                
                async with websockets.connect(uri) as websocket:
                    print(f"[Bot {username}] ¡Conectado! Comenzando a enviar datos...")
                    
                    # 3. Enviar una letra cada 1 segundo constantemente
                    while True:
                        # Generar una letra aleatoria (de la A a la Z)
                        letra = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
                        
                        # Enviar la letra por el WebSocket
                        await websocket.send(letra)
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
    tareas = [ejecutar_bot(i) for i in range(1, 22)]
    await asyncio.gather(*tareas)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSimulación detenida por el usuario.")