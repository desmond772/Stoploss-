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
            # Ensure message is always a string
            if isinstance(message, bytes):
                message = message.decode("utf-8", errors="ignore")

            # Handle handshake and keep-alive messages
            if message.startswith("0"):
                print("Received handshake response. Sending authentication...")
                auth_payload = f'42["auth",{{"session":"{POCKET_OPTION_SSID}","isDemo":0}}]'
                await websocket.send(auth_payload)
                # No longer need to manually send pings, websockets handles it
                # Start the task to request profile after authentication
                asyncio.create_task(send_profile_request_after_delay(websocket))
                continue
            elif message == "2":
                # Server sent a Socket.IO ping, respond with a pong
                # This is separate from the native WebSocket pings
                await websocket.send("3")
                continue

            # Skip large asset updates or other non-JSON messages
            if not message.startswith("42"):
                continue

            # Strip Socket.IO prefix and attempt to parse JSON
            try:
                json_payload = json.loads(message[2:])
                
                # Check for the specific 'profile' event
                if isinstance(json_payload, list) and len(json_payload) > 0 and json_payload[0] == "profile":
                    profile_info = json_payload[1]
                    balance = profile_info.get("balance")
                    demo_balance = profile_info.get("demoBalance")
                    currency = profile_info.get("currency")
                    print(f"Balance: {balance}")
                    print(f"Demo Balance: {demo_balance}")
                    print(f"Currency: {currency}")
                else:
                    event_name = json_payload[0] if isinstance(json_payload, list) and len(json_payload) > 0 else "unknown"
                    if event_name == "updateAssets":
                        print("Received updateAssets. Skipping large data.")
                    else:
                        print(f"Received event: '{event_name}' with data: {json_payload}")

            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {e} - Message: {message}")
            except Exception as e:
                print(f"Error processing message: {e}")

    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connection closed unexpectedly: {e}. Reconnecting...")
        await reconnect()

async def send_profile_request_after_delay(websocket):
    await asyncio.sleep(3)
    print("Sending profile request after delay...")
    balance_payload = '42["profile"]'
    await websocket.send(balance_payload)


async def reconnect():
    global reconnect_attempts
    if reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
        reconnect_attempts += 1
        print(f"Reconnect attempt {reconnect_attempts}...")
        await asyncio.sleep(5)
        await main()
    else:
        print("Maximum reconnect attempts exceeded. Exiting...")
        os._exit(1)


async def main():
    global reconnect_attempts
    if not WEBSOCKET_URL or not POCKET_OPTION_SSID:
        print("Error: Missing environment variables. Check your .env file.")
        return

    headers = {
        "Origin": ORIGIN,
    }

    try:
        reconnect_attempts = 0  # Reset on successful connection
        print(f"Connecting to: {WEBSOCKET_URL}")
        async with websockets.connect(
            WEBSOCKET_URL,
            additional_headers=headers,
            open_timeout=10,
            ping_interval=20, # Use the library's native ping
            ping_timeout=20,
        ) as websocket:
            print("WebSocket connection established successfully.")
            await receive_messages(websocket) # This will run until the connection closes
    except Exception as e:
        print(f"An error occurred during main connection attempt: {e}")
        await reconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nScript interrupted by user. Exiting...")
                
