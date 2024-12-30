import os
import re
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
from threading import Timer
import watchtower

# Load environment variables once
load_dotenv()
ALLOWED_DUTY_MANAGER_NUMBER = os.getenv('ALLOWED_DUTY_MANAGER_NUMBER')
ALLOWED_HOTEL_EMPLOYEE_NUMBER = os.getenv("ALLOWED_HOTEL_EMPLOYEE_NUMBER")
MAX_DELAY = int(os.getenv('MAX_DELAY', '3'))
BOT_URL = os.getenv('BOT_URL')
API_URL = os.getenv('API_URL')
TOKEN = os.getenv('TOKEN')
BOT_NUMBER = os.getenv('bot')
ROOMS = os.getenv("ROOMS")

# Set up CloudWatch logging
logger = logging.getLogger("FastAPIBot")  # Use a custom logger name for clarity
logger.setLevel(logging.INFO)

# Add CloudWatch Log Handler
cloudwatch_handler = watchtower.CloudWatchLogHandler(log_group="FastAPIBotLogs", stream_name="FastAPIBotStream")
logger.addHandler(cloudwatch_handler)

responded_messages = set()
session = requests.Session()

def update_env_var(key: str, value: str):
    """Update environment variable dynamically."""
    with open(".env", "r") as file:
        lines = file.readlines()
    updated = False
    with open(".env", "w") as file:
        for line in lines:
            if line.startswith(f"{key}="):
                file.write(f"{key}={value}\n")
                updated = True
            else:
                file.write(line)
        if not updated:
            file.write(f"{key}={value}\n")
    os.environ[key] = value

def periodic_wake_call():
    """Send periodic wake-up calls to keep the bot awake."""
    try:
        response = session.get(BOT_URL)
        # logger.info(f"Periodic wake call response: {response.status_code}")
    except Exception as e:
        logger.error(f"Error in periodic wake call: {e}")
    Timer(60, periodic_wake_call).start()

alert_messages = []
bot_active = bool(BOT_NUMBER)

# Precompile regex
ROOM_PATTERN = re.compile(
    r"(\d+)\s(?:ROOMS?|RMS?)\s*\((ECONOMY|BUSINESS)\)|(\d+)\s(?:ROOMS?|RMS?)\s(for\s(economy|business))?",
    re.IGNORECASE
)

def extract_rooms(text):
    matches = ROOM_PATTERN.findall(text)
    
    all_rooms = []
    for m in matches:
        # m is a tuple of groups: (countA, typeA, countB, typeB)
        # We'll interpret them:
        if m[0] and m[1]:
            # Matched the pattern: "<count> rooms (ECONOMY|BUSINESS)"
            room_count = int(m[0])
            room_type = m[1].lower()
        else:
            # Matched the pattern: "<count> rooms for (economy|business)"
            room_count = int(m[2])
            # m[3] is something like "for business" or "for economy"
            # if you only want "business"/"economy", you might parse further:
            room_type = m[3].replace('for ', '').lower().strip()

        all_rooms.append({
            'count': room_count,
            'type': room_type
        })

    return all_rooms

app = FastAPI(title="Airline Alert Bot")

def send_whapi_request(endpoint: str, params: Dict[str, Any] = None, method: str = 'POST') -> Dict[str, Any]:
    url = f"{API_URL}/{endpoint}"
    headers = {'Authorization': f"Bearer {TOKEN}"}
    try:
        if method == 'GET':
            resp = session.get(url, params=params, headers=headers)
        else:
            headers['Content-Type'] = 'application/json'
            resp = session.request(method, url, json=params, headers=headers)
        return resp.json()
    except Exception as e:
        logger.error(f"Error in send_whapi_request: {e}")
        return {'error': str(e)}

def set_hook():
    """Set webhook to receive messages."""
    if BOT_URL:
        settings = {
            'webhooks': [
                {
                    'url': f"{BOT_URL}/hook/messages",
                    'events': [
                        {'type': "messages", 'method': "post"},
                        {'type': "chats", 'method': "patch"},
                        {'type': "statuses", 'method': "put"}
                    ],
                    'mode': "method"
                }
            ]
        }
        send_whapi_request('settings', settings, 'PATCH')

@app.post("/hook/messages/messages")
def handle_new_messages(request_data: Dict[str, Any], background_tasks: BackgroundTasks):
    global bot_active, ALLOWED_HOTEL_EMPLOYEE_NUMBER, ALLOWED_DUTY_MANAGER_NUMBER, ROOMS, alert_messages

    if not request_data:
        raise HTTPException(status_code=400, detail="No JSON payload")

    messages = request_data.get('messages', [])
    if not messages:
        raise HTTPException(status_code=400, detail="No messages found")

    current_ts = time.time()
    immediate_response = None
    immediate_chat_id = None

    for message in messages:

        chat_name = message.get("chat_name")
        text_body = (message.get("text", {}).get("body", "")).strip().lower()
        sender = message.get("from")
        timestamp = message.get("timestamp", 0)
        bot ="@6587826208"
        # Skip old messages
        if (int(current_ts) - timestamp) > MAX_DELAY:
            continue

        # Main logic
        if chat_name == "SIA Delay Flight Alpha Group" and bot_active and sender == ALLOWED_DUTY_MANAGER_NUMBER:
            # if "sq" in text_body:
            #     rooms_found = extract_rooms(text_body)
            #     if rooms_found and rooms_found[0]['count'] <= int(ROOMS):
            #         send_whapi_request('messages/text', {'to': message.get('chat_id'), 'body': "RPS can"})
            #         alert_messages.append(text_body)
            #         end_ts = time.time()
            #         elapsed_seconds = end_ts - current_ts
            #         logger.info(f"Elapsed time in seconds:{current_ts},{end_ts},{elapsed_seconds}")
            #         # background_tasks.add_task(send_whapi_request, 'messages/text', {'to': immediate_chat_id, 'body': immediate_response})
            #         return JSONResponse({"status": "success"}, status_code=200)

            if "sq" in text_body:
                rooms_found = extract_rooms(text_body)
                # logger.info(f"Extracted rooms from text body: {rooms_found}")
                # Calculate the sum of the 'count' for all matched rooms
                sum_of_found_rooms = sum(room['count'] for room in rooms_found)
                # logger.info(f"Total rooms found = {sum_of_found_rooms}, Threshold ROOMS = {ROOMS}")
                # Compare the sum of all rooms to ROOMS
                if sum_of_found_rooms <= int(ROOMS):
                    send_whapi_request('messages/text', {'to': message.get('chat_id'), 'body': "RPS can"})
                    alert_messages.append(text_body)

                    end_ts = time.time()
                    elapsed_seconds = end_ts - current_ts
                    logger.info(f"Elapsed time in seconds: {current_ts}, {end_ts}, {elapsed_seconds}")

                    return JSONResponse({"status": "success"}, status_code=200)
            

            if "rps" in text_body and "take" in text_body and alert_messages:
                # Defer sending messages to background task
                background_tasks.add_task(process_rps_confirmation, message, alert_messages, ALLOWED_HOTEL_EMPLOYEE_NUMBER)
        
        logger.info(f"{message}")
        if chat_name == "SIA Delay Flight Alpha Group" and bot_active and "can" in text_body:
                end_ts = time.time()
                elapsed_seconds = end_ts - current_ts
                logger.info(f"Elapsed time in seconds:{text_body},{elapsed_seconds}")
                
        elif chat_name == "Internal SIA Booking confirmations":
            # Handle commands - these are less critical, can be deferred
            # Check commands and decide immediate response
            if text_body == f"{bot} start":
                bot_active = True
                immediate_response = "Application started successfully."
                immediate_chat_id = message.get('chat_id')
            elif text_body == f"{bot} shutdown":
                bot_active = False
                immediate_response = "Application shut down successfully."
                immediate_chat_id = message.get('chat_id')
            elif text_body == f"{bot} hotel number":
                immediate_response = f"The current hotel employee number is {ALLOWED_HOTEL_EMPLOYEE_NUMBER}."
                immediate_chat_id = message.get('chat_id')
            elif text_body.startswith(f"{bot} change hotel number"):
                new_num = text_body.replace(f"{bot} change hotel number", "").strip()
                if new_num:
                    # Update in background for speed
                    background_tasks.add_task(update_env_var, "ALLOWED_HOTEL_EMPLOYEE_NUMBER", new_num)
                    ALLOWED_HOTEL_EMPLOYEE_NUMBER = new_num
                    immediate_response = f"Hotel employee number updated to {new_num}."
                    immediate_chat_id = message.get('chat_id')
            elif text_body == f"{bot} airlines number":
                immediate_response = f"The current airlines number is {ALLOWED_DUTY_MANAGER_NUMBER}."
                immediate_chat_id = message.get('chat_id')
            elif text_body.startswith(f"{bot} change airlines number"):
                new_num = text_body.replace(f"{bot} change airlines number", "").strip()
                if new_num:
                    background_tasks.add_task(update_env_var, "ALLOWED_DUTY_MANAGER_NUMBER", new_num)
                    ALLOWED_DUTY_MANAGER_NUMBER = new_num
                    immediate_response = f"Airlines number updated to {new_num}."
                    immediate_chat_id = message.get('chat_id')
            elif text_body == f"{bot} view rooms":
                immediate_response = f"Available rooms: {ROOMS}"
                immediate_chat_id = message.get('chat_id')
            elif text_body.startswith(f"{bot} change rooms"):
                new_rooms = text_body.replace(f"{bot} change rooms", "").strip()
                background_tasks.add_task(update_env_var, "ROOMS", new_rooms)
                ROOMS = new_rooms
                immediate_response = f"Rooms updated to: {new_rooms}"
                immediate_chat_id = message.get('chat_id')
            elif f"{bot} help" in text_body:
                immediate_response = (
                   "You can try following messages to command the application:\n"
                    "1. To start the application, type: start\n"
                    "2. To shut down the application, type: shutdown\n"
                    "3. To view what is the airlines number, type: airlines number\n"
                    "4. To change airlines number, type:change airlines number <65xxxxxxxx>\n"
                    "5. To view hotel employee number, type: hotel number\n"
                    "6. To change hotel employee number, type: change hotel number <65xxxxxxxx>\n"
                    "7. To view available rooms, type: view rooms\n"
                    "8. To change available rooms, type: change rooms <details>\n"
                    "9. To view commands, type: help"
                )
                immediate_chat_id = message.get('chat_id')

    # Send the immediate response if any
    if immediate_response and immediate_chat_id:
        # Defer the API call to send the message in background, we respond to the request immediately
        background_tasks.add_task(send_whapi_request, 'messages/text', {'to': immediate_chat_id, 'body': immediate_response})

    return JSONResponse({"status": "success"}, status_code=200)

def process_rps_confirmation(message: Dict[str, Any], alert_messages: list, employee_number: str):
    """Process the RPS confirmation message in the background."""
    SST = timezone(timedelta(hours=8))
    stamp = message.get("timestamp")
    readable_time = datetime.fromtimestamp(stamp, SST).strftime('%Y-%m-%d %H:%M:%S')
    last_alert = alert_messages[-1]
    text_body = (message.get("text", {}).get("body", "")).strip().lower()
    full_resp = (
        f"We won a bid @{employee_number}\n"
        f"Alert received on {readable_time} (SST)\n{last_alert}\nConfirmation: {text_body}"
    )
    send_whapi_request("messages/text", {'to': str(employee_number), 'body': full_resp})
    send_whapi_request('messages/text', {'to': "120363363822984116@g.us", 'body': full_resp})

@app.patch("/hook/messages/chats")
def handle_chats():
    return JSONResponse({"status": "success"}, status_code=200)

@app.put("/hook/messages/groups")
def handle_groups():
    return JSONResponse({"status": "success"}, status_code=200)

@app.put("/hook/messages/statuses")
def handle_statuses():
    return JSONResponse({"status": "success"}, status_code=200)

@app.get("/")
def index():
    # logger.info("Health check: Bot is running")
    return "Bot is running"

@app.on_event("startup")
def startup_event():
    set_hook()
    periodic_wake_call()
