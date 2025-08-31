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
    profile_requested = False
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
                continue
            elif message == "2":
                # print("Received ping, sending pong")
                await websocket.send("3")
                continue

            # Skip large asset updates or other non-JSON messages
            if not message.startswith("42"):
                # You can add a more specific handler here if needed
                # print(f"Skipping non-JSON message or special packet: {message}")
                continue

            # Strip Socket.IO prefix and attempt to parse JSON
            try:
                # Remove the '42' prefix and parse the payload
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
                    
                # Handle other message types for debugging if needed
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

    except websockets.exceptions.ConnectionClosed:
        print("Connection closed. Reconnecting...")
        await reconnect()


async def keep_alive(websocket):
    while True:
        try:
            await websocket.send("2")
            await asyncio.sleep(10)
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed during ping. Reconnecting...")
            break
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
            
            # Use a task to send the profile request after a short delay
            async def send_profile_request_after_delay():
                await asyncio.sleep(3)  # Wait for initial asset data to pass
                print("Sending profile request after delay...")
                balance_payload = '42["profile"]'
                await websocket.send(balance_payload)
            
            tasks = [
                asyncio.create_task(receive_messages(websocket)),
                asyncio.create_task(keep_alive(websocket)),
                asyncio.create_task(send_profile_request_after_delay())
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

                                      
