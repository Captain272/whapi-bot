import os
import re
import logging
import time
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder

# Load environment variables once
load_dotenv()
ALLOWED_DUTY_MANAGER_NUMBER = os.getenv('ALLOWED_DUTY_MANAGER_NUMBER')
MAX_DELAY = int(os.getenv('MAX_DELAY', '10'))
BOT_URL = os.getenv('BOT_URL')
API_URL = os.getenv('API_URL')
TOKEN = os.getenv('TOKEN')
BOT_NUMBER = os.getenv('bot')
ALLOWED_HOTEL_EMPLOYEE_NUMBER = 919100196360

# Precompile regex
ROOM_PATTERN = re.compile(
    r"(\d+)\s(?:ROOMS?|RMS?)\s*\((ECONOMY|BUSINESS)\)|(\d+)\s(?:ROOMS?|RMS?)\s(for\s(economy|business))?",
    re.IGNORECASE
)

logging.basicConfig(level=logging.WARNING)

responded_messages = set()
alert_messages = []
bot_active = bool(BOT_NUMBER)

session = requests.Session()

app = FastAPI(title="Airline Alert Bot")

def extract_rooms(message: str):
    matches = ROOM_PATTERN.findall(message)
    result = []
    for m in matches:
        if m[0] and m[1]:  # e.g. "7 ROOMS (ECONOMY)"
            result.append({'count': int(m[0]), 'type': m[1].upper()})
        elif m[2]:  # e.g. "2 rms for economy"
            rt = m[4].upper() if m[4] else "UNKNOWN"
            result.append({'count': int(m[2]), 'type': rt})
    return result

def send_whapi_request(endpoint: str, params: Dict[str, Any] = None, method: str = 'POST') -> Dict[str, Any]:
    url = f"{API_URL}/{endpoint}"
    headers = {'Authorization': f"Bearer {TOKEN}"}
    try:
        if params and 'media' in params:
            details = params.pop('media').split(';')
            with open(details[0], 'rb') as file:
                form_data = MultipartEncoder(fields={**params, 'media': (details[0], file, details[1])})
                headers['Content-Type'] = form_data.content_type
                resp = session.request(method, url, data=form_data, headers=headers)
        elif method == 'GET':
            resp = session.get(url, params=params, headers=headers)
        else:
            headers['Content-Type'] = 'application/json'
            resp = session.request(method, url, json=params, headers=headers)
        return resp.json()
    except Exception as e:
        logging.error(f"Error in send_whapi_request: {e}")
        return {'error': str(e)}

def set_hook():
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
    start_time = time.perf_counter()  # Record start time

    global bot_active, ALLOWED_HOTEL_EMPLOYEE_NUMBER, ALLOWED_DUTY_MANAGER_NUMBER

    if not request_data:
        raise HTTPException(status_code=400, detail="No JSON payload")

    messages = request_data.get('messages', [])
    if not messages:
        raise HTTPException(status_code=400, detail="No messages found")

    current_ts = int(time.time())

    for message in messages:
        message_id = message.get("id")
        if not message_id or message_id in responded_messages:
            continue
        responded_messages.add(message_id)

        chat_name = message.get("chat_name")
        if not chat_name:
            continue

        text_body = (message.get("text", {}).get("body", "")).strip().lower()
        if not text_body:
            continue

        sender = message.get("from")
        timestamp = message.get("timestamp", 0)
        if (current_ts - timestamp) > MAX_DELAY:
            continue

        response_body = None

        # Handle Flight Delay Group
        if chat_name == "SIT - SIA Flight Delay Group Chat" and bot_active and sender == ALLOWED_DUTY_MANAGER_NUMBER:
            if "hi all" in text_body:
                rooms = extract_rooms(text_body)
                if rooms and rooms[0]['count'] < 50:
                    response_body = "RPS can"
                    alert_messages.append(text_body)

            if "rps" in text_body and "we will take" in text_body and alert_messages:
                stamp = message.get("timestamp")
                readable_time = datetime.fromtimestamp(stamp)
                last_alert = alert_messages[-1]
                full_resp = (
                    f"We won a bid @{ALLOWED_HOTEL_EMPLOYEE_NUMBER}\n"
                    f"Alert received on {readable_time}\n{last_alert}\nConfirmation: {text_body}"
                )

                send_whapi_request("messages/text", {'to': str(ALLOWED_HOTEL_EMPLOYEE_NUMBER), 'body': full_resp})
                send_whapi_request('messages/text', {'to': "120363377229741364@g.us", 'body': full_resp})

                end_time = time.perf_counter()
                elapsed = end_time - start_time
                return JSONResponse({"status": "success", "time_taken": f"{elapsed:.4f} seconds"}, status_code=200)

        # Handle Internal Group Commands
        elif chat_name == "SIT - SIA Internal Group":
            if text_body == "@916303689715 start":
                bot_active = True
                response_body = "Application started successfully."
            elif text_body == "@916303689715 shutdown":
                bot_active = False
                response_body = "Application shut down successfully."
            elif text_body == "@916303689715 hotel employee number":
                response_body = f"The current hotel employee number is {ALLOWED_HOTEL_EMPLOYEE_NUMBER}."
            elif text_body.startswith("@916303689715 change hotel employee number"):
                new_num = text_body.replace("@916303689715 change hotel employee number", "").strip()
                if new_num:
                    ALLOWED_HOTEL_EMPLOYEE_NUMBER = new_num
                    response_body = f"Hotel employee number updated to {new_num}."
            elif text_body == "@916303689715 airlines number":
                response_body = f"The current airlines number is {ALLOWED_DUTY_MANAGER_NUMBER}."
            elif text_body.startswith("@916303689715 change airlines number"):
                new_num = text_body.replace("@916303689715 change airlines number", "").strip()
                if new_num:
                    ALLOWED_DUTY_MANAGER_NUMBER = new_num
                    response_body = f"Airlines number updated to {new_num}."
            elif "@916303689715 help" in text_body:
                response_body = (
                    "You can try following messages to command the bot:\n"
                    "1. To start the application, type: start\n"
                    "2. To shut down the application, type: shutdown\n"
                    "3. To view hotel employee number, type: hotel employee number\n"
                    "4. To change hotel employee number, type: change hotel employee number <number>\n"
                    "5. To view what is the airlines number, type: airlines number\n"
                    "6. To change airlines number, type: change airlines number <65xxxxxxxx>\n"
                    "7. To view commands, type: help"
                )

        # Send a response if any was constructed
        if response_body:
            send_whapi_request('messages/text', {'to': message.get('chat_id'), 'body': response_body})
            end_time = time.perf_counter()
            elapsed = end_time - start_time
            send_whapi_request('messages/text', {'to': message.get('chat_id'), 'body': "Response time : "+ str(elapsed)+" sec"})

    # If no early return occurred, measure the total time at the end

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

@app.on_event("startup")
def startup_event():
    set_hook()

