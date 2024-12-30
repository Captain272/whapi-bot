# import os
# import re
# import logging
# import time
# from datetime import datetime,timezone, timedelta

# from typing import Any, Dict

# from fastapi import FastAPI, HTTPException
# from fastapi.responses import JSONResponse
# from dotenv import load_dotenv
# import requests
# from requests_toolbelt.multipart.encoder import MultipartEncoder
# from threading import Timer

# # Load environment variables once
# load_dotenv()
# ALLOWED_DUTY_MANAGER_NUMBER = os.getenv('ALLOWED_DUTY_MANAGER_NUMBER')
# ALLOWED_HOTEL_EMPLOYEE_NUMBER = os.getenv("ALLOWED_HOTEL_EMPLOYEE_NUMBER")
# MAX_DELAY = int(os.getenv('MAX_DELAY', '3'))
# BOT_URL = os.getenv('BOT_URL')
# API_URL = os.getenv('API_URL')
# TOKEN = os.getenv('TOKEN')
# BOT_NUMBER = os.getenv('bot')
# ROOMS = os.getenv("ROOMS")

# # Precompile regex
# ROOM_PATTERN = re.compile(
#     r"(\d+)\s(?:ROOMS?|RMS?)\s*\((ECONOMY|BUSINESS)\)|(\d+)\s(?:ROOMS?|RMS?)\s(for\s(economy|business))?",
#     re.IGNORECASE
# )

# # Logging setup
# # logging.basicConfig(filename="bot_logs.log", level=logging.INFO,
# #                     format="%(asctime)s - %(levelname)s - %(message)s")

# responded_messages = set()
# session = requests.Session()


# def update_env_var(key: str, value: str):
#     """Update environment variable dynamically."""
#     with open(".env", "r") as file:
#         lines = file.readlines()
#     updated = False
#     with open(".env", "w") as file:
#         for line in lines:
#             if line.startswith(f"{key}="):
#                 file.write(f"{key}={value}\n")
#                 updated = True
#             else:
#                 file.write(line)
#         if not updated:
#             file.write(f"{key}={value}\n")
#     os.environ[key] = value


# def periodic_wake_call():
#     """Send periodic wake-up calls to keep the bot awake."""
#     try:
#         response = session.get(BOT_URL)
#         # logging.info(f"Periodic call response: {response.status_code}")
#     except Exception as e:
#         # logging.error(f"Error in periodic wake call: {e}")
#         pass
#     Timer(6, periodic_wake_call).start()


# alert_messages = []
# bot_active = bool(BOT_NUMBER)

# session = requests.Session()

# app = FastAPI(title="Airline Alert Bot")

# def extract_rooms(message: str):
#     matches = ROOM_PATTERN.findall(message)
#     result = []
#     for m in matches:
#         if m[0] and m[1]:  # e.g. "7 ROOMS (ECONOMY)"
#             result.append({'count': int(m[0]), 'type': m[1].upper()})
#         elif m[2]:  # e.g. "2 rms for economy"
#             rt = m[4].upper() if m[4] else "UNKNOWN"
#             result.append({'count': int(m[2]), 'type': rt})
#     return result

# def send_whapi_request(endpoint: str, params: Dict[str, Any] = None, method: str = 'POST') -> Dict[str, Any]:
#     url = f"{API_URL}/{endpoint}"
#     headers = {'Authorization': f"Bearer {TOKEN}"}
#     try:
#         if params and 'media' in params:
#             details = params.pop('media').split(';')
#             with open(details[0], 'rb') as file:
#                 form_data = MultipartEncoder(fields={**params, 'media': (details[0], file, details[1])})
#                 headers['Content-Type'] = form_data.content_type
#                 resp = session.request(method, url, data=form_data, headers=headers)
#         elif method == 'GET':
#             resp = session.get(url, params=params, headers=headers)
#         else:
#             headers['Content-Type'] = 'application/json'
#             resp = session.request(method, url, json=params, headers=headers)
#         return resp.json()
#     except Exception as e:
#         logging.error(f"Error in send_whapi_request: {e}")
#         return {'error': str(e)}

# def set_hook():
#     if BOT_URL:
#         settings = {
#             'webhooks': [
#                 {
#                     'url': f"{BOT_URL}/hook/messages",
#                     'events': [
#                         {'type': "messages", 'method': "post"},
#                         {'type': "chats", 'method': "patch"},
#                         {'type': "statuses", 'method': "put"}
#                     ],
#                     'mode': "method"
#                 }
#             ]
#         }
#         send_whapi_request('settings', settings, 'PATCH')



# @app.on_event("startup")
# def startup_event():
#     set_hook()
#     periodic_wake_call()

# @app.post("/hook/messages/messages")
# def handle_new_messages(request_data: Dict[str, Any]):
#     start_time = time.perf_counter()  # Record start time

#     global bot_active, ALLOWED_HOTEL_EMPLOYEE_NUMBER, ALLOWED_DUTY_MANAGER_NUMBER,ROOMS

#     if not request_data:
#         raise HTTPException(status_code=400, detail="No JSON payload")

#     messages = request_data.get('messages', [])
#     if not messages:
#         raise HTTPException(status_code=400, detail="No messages found")

#     current_ts = int(time.time())

#     for message in messages:
#         message_id = message.get("id")
#         if not message_id or message_id in responded_messages:
#             continue
#         responded_messages.add(message_id)

#         chat_name = message.get("chat_name")
#         if not chat_name:
#             continue

#         text_body = (message.get("text", {}).get("body", "")).strip().lower()
#         if not text_body:
#             continue

#         sender = message.get("from")
#         timestamp = message.get("timestamp", 0)
#         if (current_ts - timestamp) > MAX_DELAY:
#             continue

#         response_body = None

#         # Handle Flight Delay Group
#         if chat_name == "SIT - SIA Flight Delay Group Chat" and bot_active and sender == ALLOWED_DUTY_MANAGER_NUMBER:
#             if "hi all" in text_body:
#                 rooms = extract_rooms(text_body)
#                 if rooms and rooms[0]['count'] < int(ROOMS):
#                     response_body = "RPS can"
#                     alert_messages.append(text_body)

#             if "rps" in text_body and "we will take" in text_body and alert_messages:
#                 SST = timezone(timedelta(hours=8))

#                 stamp = message.get("timestamp")
#                 readable_time = datetime.fromtimestamp(stamp, SST).strftime('%Y-%m-%d %H:%M:%S')
#                 last_alert = alert_messages[-1]
#                 full_resp = (
#                     f"We won a bid @{ALLOWED_HOTEL_EMPLOYEE_NUMBER}\n"
#                     f"Alert received on {readable_time} (SST)\n{last_alert}\nConfirmation: {text_body}"
#                 )

#                 send_whapi_request("messages/text", {'to': str(ALLOWED_HOTEL_EMPLOYEE_NUMBER), 'body': full_resp})
#                 send_whapi_request('messages/text', {'to': "120363377229741364@g.us", 'body': full_resp})

#                 end_time = time.perf_counter()
#                 elapsed = end_time - start_time
#                 return JSONResponse({"status": "success", "time_taken": f"{elapsed:.4f} seconds"}, status_code=200)

#         # Handle Internal Group Commands
#         elif chat_name == "SIT - SIA Internal Group":
#             if text_body == "@6587826208 start":
#                 bot_active = True
#                 response_body = "Application started successfully."
#             elif text_body == "@6587826208 shutdown":
#                 bot_active = False
#                 response_body = "Application shut down successfully."
#             elif text_body == "@6587826208 hotel number":
#                 response_body = f"The current hotel employee number is {ALLOWED_HOTEL_EMPLOYEE_NUMBER}."
#             elif text_body.startswith("@6587826208 change hotel number"):
#                 new_num = text_body.replace("@6587826208 change hotel number", "").strip()
#                 if new_num:
#                     ALLOWED_HOTEL_EMPLOYEE_NUMBER = new_num
#                     response_body = f"Hotel employee number updated to {new_num}."
#                     update_env_var("ALLOWED_HOTEL_EMPLOYEE_NUMBER", new_num)
#             elif text_body == "@6587826208 airlines number":
#                 response_body = f"The current airlines number is {ALLOWED_DUTY_MANAGER_NUMBER}."
#             elif text_body.startswith("@6587826208 change airlines number"):
#                 new_num = text_body.replace("@6587826208 change airlines number", "").strip()
#                 if new_num:
#                     ALLOWED_DUTY_MANAGER_NUMBER = new_num
#                     response_body = f"Airlines number updated to {new_num}."
#                     update_env_var("ALLOWED_DUTY_MANAGER_NUMBER", new_num)

#             elif text_body == "@6587826208 view rooms":
#                 response_body = f"Available rooms: {ROOMS}"

#             elif text_body.startswith("@6587826208 change rooms"):
#                 new_rooms = text_body.replace("@6587826208 change rooms", "").strip()
#                 ROOMS = new_rooms
#                 update_env_var("ROOMS", new_rooms)
#                 response_body = f"Rooms updated to: {new_rooms}"
#             elif "@6587826208 help" in text_body:
#                 response_body = (
#                     "You can try following messages to command the application:\n"
#                     "1. To start the application, type: start\n"
#                     "2. To shut down the application, type: stop\n"
#                     "3. To view what is the airlines number, type: airlines number\n"
#                     "4. To change airlines number, type:change airlines number <65xxxxxxxx>\n"
#                     "5. To view hotel employee number, type: hotel number\n"
#                     "6. To change hotel employee number, type: change hotel number <65xxxxxxxx>\n"
#                     "7. To view available rooms, type: view rooms\n"
#                     "8. To change available rooms, type: change rooms <details>\n"
#                     "9. To view commands, type: help"
#                 )

#         # Send a response if any was constructed
#         if response_body:
#             send_whapi_request('messages/text', {'to': message.get('chat_id'), 'body': response_body})
#             end_time = time.perf_counter()
#             elapsed = end_time - start_time
#             send_whapi_request('messages/text', {'to': message.get('chat_id'), 'body': "Response time : "+ str(elapsed)+" sec"})

#     # If no early return occurred, measure the total time at the end

#     return JSONResponse({"status": "success"}, status_code=200)

# @app.patch("/hook/messages/chats")
# def handle_chats():
#     return JSONResponse({"status": "success"}, status_code=200)

# @app.put("/hook/messages/groups")
# def handle_groups():
#     return JSONResponse({"status": "success"}, status_code=200)

# @app.put("/hook/messages/statuses")
# def handle_statuses():
#     return JSONResponse({"status": "success"}, status_code=200)

# @app.get("/")
# def index():
#     return "Bot is running"

# @app.on_event("startup")
# def startup_event():
#     set_hook()



import os
import re
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
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

# Remove any default console handlers
for handler in logger.handlers:
    if isinstance(handler, logging.StreamHandler):
        logger.removeHandler(handler)

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
        logger.info(f"Periodic wake call response: {response.status_code}")
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

# def extract_rooms(message: str):
#     matches = ROOM_PATTERN.findall(message)
#     result = []
#     for m in matches:
#         if m[0] and m[1]:  # e.g. "7 ROOMS (ECONOMY)"
#             result.append({'count': int(m[0]), 'type': m[1].upper()})
#         elif m[2]:  # e.g. "2 rms for economy"
#             rt = m[4].upper() if m[4] else "UNKNOWN"
#             result.append({'count': int(m[2]), 'type': rt})
#     return result


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
        logger.info(f"Sending request to {url} with params: {params}")
        if method == 'GET':
            resp = session.get(url, params=params, headers=headers)
        else:
            headers['Content-Type'] = 'application/json'
            resp = session.request(method, url, json=params, headers=headers)
        response_data = resp.json()
        logger.info(f"Response from {url}: {response_data}")
        return response_data
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
def handle_new_messages(request_data: Dict[str, Any]):
    logger.info(f"Webhook received data: {request_data}")
    global bot_active, ALLOWED_HOTEL_EMPLOYEE_NUMBER, ALLOWED_DUTY_MANAGER_NUMBER, ROOMS

    if not request_data:
        logger.error("No JSON payload in request")
        raise HTTPException(status_code=400, detail="No JSON payload")

    messages = request_data.get('messages', [])
    if not messages:
        logger.warning("No messages found in webhook data")
        raise HTTPException(status_code=400, detail="No messages found")

    current_ts = int(time.time())
    for message in messages:
        message_id = message.get("id")
        if not message_id or message_id in responded_messages:
            continue
        responded_messages.add(message_id)

        chat_name = message.get("chat_name")
        text_body = (message.get("text", {}).get("body", "")).strip().lower()
        sender = message.get("from")
        timestamp = message.get("timestamp", 0)

        if (current_ts - timestamp) > MAX_DELAY:
            logger.warning(f"Message {message_id} skipped due to delay")
            continue

        logger.info(f"Processing message: {text_body} from chat: {chat_name,sender,ALLOWED_DUTY_MANAGER_NUMBER,ALLOWED_HOTEL_EMPLOYEE_NUMBER}")

        response_body = None

        # Handle Flight Delay Group
        if chat_name == "SIA Delay Flight Alpha Group" and bot_active and sender == ALLOWED_DUTY_MANAGER_NUMBER:
            logger.info(f"Got Alert: {text_body}")

            if "sq" in text_body:
                # Add detailed logger
                rooms = extract_rooms(text_body)
                logger.info(f"Extracted rooms: {rooms , rooms[0]['count'] ,int(ROOMS)}")
                # logger.info(f"Extracted rooms: {rooms}")
                if rooms and rooms[0]['count'] < int(ROOMS):
                    response_body = "RPS can"
                    alert_messages.append(text_body)

            if "rps" in text_body and "we will take" in text_body and alert_messages:
                SST = timezone(timedelta(hours=8))
                stamp = message.get("timestamp")
                readable_time = datetime.fromtimestamp(stamp, SST).strftime('%Y-%m-%d %H:%M:%S')
                last_alert = alert_messages[-1]
                full_resp = (
                    f"We won a bid @{ALLOWED_HOTEL_EMPLOYEE_NUMBER}\n"
                    f"Alert received on {readable_time} (SST)\n{last_alert}\nConfirmation: {text_body}"
                )
                send_whapi_request("messages/text", {'to': str(ALLOWED_HOTEL_EMPLOYEE_NUMBER), 'body': full_resp})
                send_whapi_request('messages/text', {'to': "120363363822984116@g.us", 'body': full_resp})
         # Handle Internal Group Commands UAT - SIA Internal Group Internal SIA Booking confirmations
        elif chat_name == "Internal SIA Booking confirmations":

            if text_body == "@6587826208 start":
                bot_active = True
                response_body = "Application started successfully."
            elif text_body == "@6587826208 shutdown":
                bot_active = False
                response_body = "Application shut down successfully."
            elif text_body == "@6587826208 hotel number":
                response_body = f"The current hotel employee number is {ALLOWED_HOTEL_EMPLOYEE_NUMBER}."
            elif text_body.startswith("@6587826208 change hotel number"):
                new_num = text_body.replace("@6587826208 change hotel number", "").strip()
                if new_num:
                    ALLOWED_HOTEL_EMPLOYEE_NUMBER = new_num
                    response_body = f"Hotel employee number updated to {new_num}."
                    update_env_var("ALLOWED_HOTEL_EMPLOYEE_NUMBER", new_num)
            elif text_body == "@6587826208 airlines number":
                response_body = f"The current airlines number is {ALLOWED_DUTY_MANAGER_NUMBER}."
            elif text_body.startswith("@6587826208 change airlines number"):
                new_num = text_body.replace("@6587826208 change airlines number", "").strip()
                if new_num:
                    ALLOWED_DUTY_MANAGER_NUMBER = new_num
                    response_body = f"Airlines number updated to {new_num}."
                    update_env_var("ALLOWED_DUTY_MANAGER_NUMBER", new_num)

            elif text_body == "@6587826208 view rooms":
                response_body = f"Available rooms: {ROOMS}"

            elif text_body.startswith("@6587826208 change rooms"):
                new_rooms = text_body.replace("@6587826208 change rooms", "").strip()
                ROOMS = new_rooms
                update_env_var("ROOMS", new_rooms)
                response_body = f"Rooms updated to: {new_rooms}"
            elif "@6587826208 help" in text_body:
                response_body = (
                    "You can try following messages to command the application:\n"
                    "1. To start the application, type: start\n"
                    "2. To shut down the application, type: stop\n"
                    "3. To view what is the airlines number, type: airlines number\n"
                    "4. To change airlines number, type:change airlines number <65xxxxxxxx>\n"
                    "5. To view hotel employee number, type: hotel number\n"
                    "6. To change hotel employee number, type: change hotel number <65xxxxxxxx>\n"
                    "7. To view available rooms, type: view rooms\n"
                    "8. To change available rooms, type: change rooms <details>\n"
                    "9. To view commands, type: help"
                )
        # Add more command handling logic here as per your requirements

        # Send response
        if response_body:
            send_whapi_request('messages/text', {'to': message.get('chat_id'), 'body': response_body})

    return JSONResponse({"status": "success"}, status_code=200)

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
    return "Bot is running"

@app.get("/")
def index():
    logger.info("Health check: Bot is running")
    return "Bot is running"

@app.on_event("startup")
def startup_event():
    set_hook()
    periodic_wake_call()
