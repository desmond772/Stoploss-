import os
import asyncio
import json
import websockets
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get environment variables
POCKET_OPTION_SSID = os.getenv("POCKET_OPTION_SSID")
WEBSOCKET_URL = os.getenv("WEBSOCKET_URL")
ORIGIN = os.getenv("ORIGIN")

MAX_RECONNECT_ATTEMPTS = 5
reconnect_attempts = 0


async def receive_messages(websocket):
    try:
        async for message in websocket:
            # Ensure message is always string
            if isinstance(message, bytes):
                message = message.decode("utf-8", errors="ignore")

            if message.startswith("0"):
                print("Received handshake response. Sending authentication...")
                auth_payload = (
                    f'42["auth",{{"session":"{POCKET_OPTION_SSID}","isDemo":0}}]'
                )
                await websocket.send(auth_payload)

            elif message.startswith("40"):
                print("Received authentication response. Sending profile request...")
                balance_payload = '42["profile"]'
                await websocket.send(balance_payload)

            elif message.startswith('42["profile"'):
                try:
                    profile_info = json.loads(message[3:])[1]
                    balance = profile_info.get("balance")
                    demo_balance = profile_info.get("demoBalance")
                    currency = profile_info.get("currency")
                    print(f"Balance: {balance}")
                    print(f"Demo Balance: {demo_balance}")
                    print(f"Currency: {currency}")
                except Exception as e:
                    print(f"Error parsing profile: {e}")

            elif message == "2":
                print("Received ping, sending pong")
                await websocket.send("3")

            else:
                print(f"Received message: {message}")

    except websockets.exceptions.ConnectionClosed:
        print("Connection closed. Reconnecting...")
        await reconnect()


async def keep_alive(websocket):
    while True:
        try:
            await websocket.send("2")
            print("Ping sent successfully.")
            await asyncio.sleep(10)
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed. Reconnecting...")
            await reconnect()
        except Exception as e:
            print(f"Error sending ping: {e}")


async def reconnect():
    global reconnect_attempts
    if reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
        reconnect_attempts += 1
        print(f"Reconnect attempt {reconnect_attempts}...")
        await asyncio.sleep(5)
        await main()
    else:
        print("Maximum reconnect attempts exceeded. Exiting...")


async def main():
    if not WEBSOCKET_URL or not POCKET_OPTION_SSID:
        print("Error: Missing environment variables. Check your .env file.")
        return

    headers = {
        "Origin": ORIGIN,
    }

    try:
        print(f"Connecting to: {WEBSOCKET_URL}")
        async with websockets.connect(
            WEBSOCKET_URL,
            additional_headers=headers,
            open_timeout=10,
            ping_interval=None,
        ) as websocket:
            print("WebSocket connection established successfully.")
            tasks = [
                asyncio.create_task(receive_messages(websocket)),
                asyncio.create_task(keep_alive(websocket)),
            ]
            await asyncio.gather(*tasks)
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nScript interrupted by user. Exiting...")
    except Exception as e:
        print(f"An error occurred: {e}")
