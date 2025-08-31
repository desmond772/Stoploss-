import os
import asyncio
import json
import websockets
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging configuration
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("stoploss.log"),
        logging.StreamHandler()
    ]
)

# Get environment variables
POCKET_OPTION_SSID = os.getenv("POCKET_OPTION_SSID")
WEBSOCKET_URL = os.getenv("WEBSOCKET_URL")
ORIGIN = os.getenv("ORIGIN")

MAX_RECONNECT_ATTEMPTS = 5
reconnect_attempts = 0


async def receive_messages(websocket):
    try:
        async for message in websocket:
            if isinstance(message, bytes):
                message = message.decode("utf-8", errors="ignore")

            # Handle handshake and keep-alive messages
            if message.startswith("0"):
                logging.info("Received handshake response. Sending authentication...")
                # --- CHANGE IS HERE: isDemo is now set to 1 for a demo account ---
                auth_payload = f'42["auth",{{"session":"{POCKET_OPTION_SSID}","isDemo":1}}]'
                await websocket.send(auth_payload)
                asyncio.create_task(send_profile_request_after_delay(websocket))
                continue
            elif message == "2":
                await websocket.send("3")
                continue

            if not message.startswith("42"):
                continue

            try:
                json_payload = json.loads(message[2:])
                event_name = json_payload[0] if isinstance(json_payload, list) and len(json_payload) > 0 else "unknown"

                if event_name == "profile":
                    profile_info = json_payload[1]
                    balance = profile_info.get("balance")
                    demo_balance = profile_info.get("demoBalance")
                    is_demo = profile_info.get("isDemo")
                    currency = profile_info.get("currency")
                    
                    if is_demo == 0:
                        logging.info("Connected to LIVE server. Retrieving balance...")
                        logging.info(f"Live Balance: {balance} {currency}")
                    else:
                        logging.info("Connected to DEMO server. Retrieving balance...")
                        logging.info(f"Demo Balance: {demo_balance} {currency}")

                elif event_name == "auth":
                    auth_status = json_payload[1].get("status")
                    if auth_status == "ok":
                        logging.info("Authentication successful.")
                    else:
                        logging.error(f"Authentication failed: {auth_status}")

                elif event_name == "updateAssets":
                    logging.info("Received market data update (updateAssets). Skipping large data.")

                else:
                    logging.debug(f"Received event: '{event_name}' with data: {json_payload}")

            except json.JSONDecodeError as e:
                logging.error(f"Error parsing JSON: {e} - Message: {message}")
            except Exception as e:
                logging.error(f"Error processing message: {e}")

    except websockets.exceptions.ConnectionClosed as e:
        logging.warning(f"Connection closed unexpectedly: {e}. Reconnecting...")
        await reconnect()
    except Exception as e:
        logging.error(f"An error occurred in receive_messages: {e}")
        await reconnect()


async def send_profile_request_after_delay(websocket):
    try:
        await asyncio.sleep(3)
        balance_payload = '42["profile"]'
        await websocket.send(balance_payload)
        logging.info("Profile request sent successfully.")
    except websockets.exceptions.ConnectionClosed as e:
        logging.error(f"Failed to send profile request: Connection was closed. {e}")
    except Exception as e:
        logging.error(f"Error sending profile request: {e}")


async def reconnect():
    global reconnect_attempts
    if reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
        reconnect_attempts += 1
        logging.info(f"Reconnect attempt {reconnect_attempts}...")
        await asyncio.sleep(5)
        await main()
    else:
        logging.critical("Maximum reconnect attempts exceeded. Exiting...")
        os._exit(1)


async def main():
    global reconnect_attempts
    if not WEBSOCKET_URL or not POCKET_OPTION_SSID:
        logging.critical("Error: Missing environment variables. Check your .env file.")
        return

    headers = {
        "Origin": ORIGIN,
    }

    try:
        reconnect_attempts = 0
        logging.info(f"Connecting to: {WEBSOCKET_URL}")
        async with websockets.connect(
            WEBSOCKET_URL,
            additional_headers=headers,
            open_timeout=10,
            ping_interval=20,
            ping_timeout=20,
        ) as websocket:
            logging.info("WebSocket connection established successfully.")
            await receive_messages(websocket)
    except Exception as e:
        logging.error(f"An error occurred during main connection attempt: {e}")
        await reconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("\nScript interrupted by user. Exiting...")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

