# import os
# import re
# import logging
# import time
# from datetime import datetime
# from typing import Any, Dict
# from fastapi import FastAPI, HTTPException, BackgroundTasks
# from fastapi.responses import JSONResponse
# from dotenv import load_dotenv
# import requests
# from requests_toolbelt.multipart.encoder import MultipartEncoder
# import httpx
# from functools import lru_cache

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

# responded_messages = set()
# alert_messages = []
# bot_active = bool(BOT_NUMBER)
# http_client = httpx.AsyncClient()

# # Initialize FastAPI app
# app = FastAPI(title="Airline Alert Bot")

# async def update_env_var(key: str, value: str):
#     """Update environment variable dynamically."""
#     try:
#         with open(".env", "r") as file:
#             lines = file.readlines()
#         updated = False
#         with open(".env", "w") as file:
#             for line in lines:
#                 if line.startswith(f"{key}="):
#                     file.write(f"{key}={value}\n")
#                     updated = True
#                 else:
#                     file.write(line)
#             if not updated:
#                 file.write(f"{key}={value}\n")
#         os.environ[key] = value
#     except Exception as e:
#         logging.error(f"Error updating environment variable: {e}")

# @lru_cache(maxsize=100)
# def extract_rooms(message: str):
#     """Extract room information from message with caching."""
#     matches = ROOM_PATTERN.findall(message)
#     result = []
#     for m in matches:
#         if m[0] and m[1]:  # e.g. "7 ROOMS (ECONOMY)"
#             result.append({'count': int(m[0]), 'type': m[1].upper()})
#         elif m[2]:  # e.g. "2 rms for economy"
#             rt = m[4].upper() if m[4] else "UNKNOWN"
#             result.append({'count': int(m[2]), 'type': rt})
#     return result

# async def send_whapi_request(endpoint: str, params: Dict[str, Any] = None, method: str = 'POST') -> Dict[str, Any]:
#     """Send request to WhatsApp API with async support."""
#     url = f"{API_URL}/{endpoint}"
#     headers = {'Authorization': f"Bearer {TOKEN}"}
    
#     try:
#         if params and 'media' in params:
#             # Handle media uploads synchronously as they require file operations
#             details = params.pop('media').split(';')
#             with open(details[0], 'rb') as file:
#                 form_data = MultipartEncoder(fields={**params, 'media': (details[0], file, details[1])})
#                 headers['Content-Type'] = form_data.content_type
#                 async with httpx.AsyncClient() as client:
#                     response = await client.request(method, url, data=form_data, headers=headers)
#         else:
#             headers['Content-Type'] = 'application/json'
#             async with httpx.AsyncClient() as client:
#                 if method == 'GET':
#                     response = await client.get(url, params=params, headers=headers)
#                 else:
#                     response = await client.request(method, url, json=params, headers=headers)
        
#         return response.json()
#     except Exception as e:
#         logging.error(f"Error in send_whapi_request: {e}")
#         return {'error': str(e)}

# @app.on_event("startup")
# async def startup_event():
#     """Initialize webhook on startup."""
#     if BOT_URL:
#         settings = {
#             'webhooks': [{
#                 'url': f"{BOT_URL}/hook/messages",
#                 'events': [
#                     {'type': "messages", 'method': "post"},
#                     {'type': "chats", 'method': "patch"},
#                     {'type': "statuses", 'method': "put"}
#                 ],
#                 'mode': "method"
#             }]
#         }
#         await send_whapi_request('settings', settings, 'PATCH')

# @app.post("/hook/messages/messages")
# async def handle_new_messages(request_data: Dict[str, Any], background_tasks: BackgroundTasks):
#     start_time = time.perf_counter()

#     global bot_active, ALLOWED_HOTEL_EMPLOYEE_NUMBER, ALLOWED_DUTY_MANAGER_NUMBER, ROOMS

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
#                 stamp = message.get("timestamp")
#                 readable_time = datetime.fromtimestamp(stamp)
#                 last_alert = alert_messages[-1]
#                 full_resp = (
#                     f"We won a bid @{ALLOWED_HOTEL_EMPLOYEE_NUMBER}\n"
#                     f"Alert received on {readable_time}\n{last_alert}\n"
#                     f"Confirmation: {text_body}"
#                 )

#                 # Send notifications concurrently
#                 background_tasks.add_task(
#                     send_whapi_request,
#                     "messages/text",
#                     {'to': str(ALLOWED_HOTEL_EMPLOYEE_NUMBER), 'body': full_resp}
#                 )
#                 background_tasks.add_task(
#                     send_whapi_request,
#                     'messages/text',
#                     {'to': "120363377229741364@g.us", 'body': full_resp}
#                 )

#         # Handle Internal Group Commands
#         elif chat_name == "SIT - SIA Internal Group":
#             bot_mention = "@916303689715"
            
#             if text_body == f"{bot_mention} start":
#                 bot_active = True
#                 response_body = "Application started successfully."
#             elif text_body == f"{bot_mention} shutdown":
#                 bot_active = False
#                 response_body = "Application shut down successfully."
#             elif text_body == f"{bot_mention} hotel number":
#                 response_body = f"The current hotel employee number is {ALLOWED_HOTEL_EMPLOYEE_NUMBER}."
#             elif text_body.startswith(f"{bot_mention} change hotel number"):
#                 new_num = text_body.replace(f"{bot_mention} change hotel number", "").strip()
#                 if new_num:
#                     ALLOWED_HOTEL_EMPLOYEE_NUMBER = new_num
#                     response_body = f"Hotel employee number updated to {new_num}."
#                     background_tasks.add_task(update_env_var, "ALLOWED_HOTEL_EMPLOYEE_NUMBER", new_num)
#             elif text_body == f"{bot_mention} airlines number":
#                 response_body = f"The current airlines number is {ALLOWED_DUTY_MANAGER_NUMBER}."
#             elif text_body.startswith(f"{bot_mention} change airlines number"):
#                 new_num = text_body.replace(f"{bot_mention} change airlines number", "").strip()
#                 if new_num:
#                     ALLOWED_DUTY_MANAGER_NUMBER = new_num
#                     response_body = f"Airlines number updated to {new_num}."
#                     background_tasks.add_task(update_env_var, "ALLOWED_DUTY_MANAGER_NUMBER", new_num)
#             elif text_body == f"{bot_mention} view rooms":
#                 response_body = f"Available rooms: {ROOMS}"
#             elif text_body.startswith(f"{bot_mention} change rooms"):
#                 new_rooms = text_body.replace(f"{bot_mention} change rooms", "").strip()
#                 if new_rooms:
#                     ROOMS = new_rooms
#                     background_tasks.add_task(update_env_var, "ROOMS", new_rooms)
#                     response_body = f"Rooms updated to: {new_rooms}"
#             elif f"{bot_mention} help" in text_body:
#                 response_body = (
#                     "Available commands:\n"
#                     "1. start - Start the application\n"
#                     "2. shutdown - Shut down the application\n"
#                     "3. hotel number - View hotel employee number\n"
#                     "4. airlines number - View airlines number\n"
#                     "5. change hotel number <number> - Update hotel number\n"
#                     "6. change airlines number <number> - Update airlines number\n"
#                     "7. view rooms - View available rooms\n"
#                     "8. change rooms <number> - Update available rooms\n"
#                     "9. help - View this message"
#                 )

#         # Send response if any was constructed
#         if response_body:
#             await send_whapi_request('messages/text', {'to': message.get('chat_id'), 'body': response_body})
#             elapsed = time.perf_counter() - start_time
#             await send_whapi_request('messages/text', {'to': message.get('chat_id'), 'body': f"Response time: {elapsed:.4f} sec"})

#     elapsed = time.perf_counter() - start_time
#     return JSONResponse({
#         "status": "success",
#         "time_taken": f"{elapsed:.4f} seconds"
#     }, status_code=200)

# @app.patch("/hook/messages/chats")
# async def handle_chats():
#     return JSONResponse({"status": "success"}, status_code=200)

# @app.put("/hook/messages/groups")
# async def handle_groups():
#     return JSONResponse({"status": "success"}, status_code=200)

# @app.put("/hook/messages/statuses")
# async def handle_statuses():
#     return JSONResponse({"status": "success"}, status_code=200)

# @app.get("/")
# async def index():
#     return "Bot is running"

# # Cleanup on shutdown
# @app.on_event("shutdown")
# async def shutdown_event():
#     await http_client.aclose()


import os
import re
import time
import asyncio
from datetime import datetime
from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import httpx
from functools import lru_cache

# Load environment variables once
load_dotenv()
settings = {
    'ALLOWED_DUTY_MANAGER_NUMBER': os.getenv('ALLOWED_DUTY_MANAGER_NUMBER'),
    'ALLOWED_HOTEL_EMPLOYEE_NUMBER': os.getenv("ALLOWED_HOTEL_EMPLOYEE_NUMBER"),
    'MAX_DELAY': int(os.getenv('MAX_DELAY', '3')),
    'BOT_URL': os.getenv('BOT_URL'),
    'API_URL': os.getenv('API_URL'),
    'TOKEN': os.getenv('TOKEN'),
    'ROOMS': os.getenv("ROOMS"),
    'bot_active': bool(os.getenv('bot'))
}

# Precompile regex and create shared client
ROOM_PATTERN = re.compile(r"(\d+)\s(?:ROOMS?|RMS?)\s*\((ECONOMY|BUSINESS)\)|(\d+)\s(?:ROOMS?|RMS?)\s(for\s(economy|business))?", re.IGNORECASE)
responded_messages = set()
alert_messages = []
http_client = httpx.AsyncClient(timeout=30.0, limits=httpx.Limits(max_keepalive_connections=100, max_connections=100))

app = FastAPI(title="Airline Alert Bot")

@lru_cache(maxsize=100)
def extract_rooms(message: str) -> List[Dict]:
    matches = ROOM_PATTERN.findall(message)
    return [
        {'count': int(m[0]), 'type': m[1].upper()} if m[0] and m[1]
        else {'count': int(m[2]), 'type': m[4].upper() if m[4] else "UNKNOWN"}
        for m in matches if m[0] or m[2]
    ]

async def send_whapi_request(messages: List[Dict]) -> List[Dict]:
    """Batch send messages to WhatsApp API"""
    if not messages:
        return []
    
    url = f"{settings['API_URL']}/messages/text"
    headers = {
        'Authorization': f"Bearer {settings['TOKEN']}",
        'Content-Type': 'application/json'
    }
    
    async def send_single(msg):
        try:
            response = await http_client.post(url, json=msg, headers=headers)
            return response.json()
        except Exception as e:
            return {'error': str(e)}

    return await asyncio.gather(*[send_single(msg) for msg in messages])

async def process_flight_delay_message(message: Dict, text_body: str, current_ts: int) -> List[Dict]:
    """Process messages from flight delay group"""
    responses = []
    
    if "hi all" in text_body:
        rooms = extract_rooms(text_body)
        if rooms and rooms[0]['count'] < int(settings['ROOMS']):
            alert_messages.append(text_body)
            responses.append({
                'to': message.get('chat_id'),
                'body': "RPS can"
            })
    
    elif "rps" in text_body and "we will take" in text_body and alert_messages:
        last_alert = alert_messages[-1]
        notification = (
            f"We won a bid @{settings['ALLOWED_HOTEL_EMPLOYEE_NUMBER']}\n"
            f"Alert received on {datetime.fromtimestamp(message['timestamp'])}\n"
            f"{last_alert}\nConfirmation: {text_body}"
        )
        
        responses.extend([
            {'to': str(settings['ALLOWED_HOTEL_EMPLOYEE_NUMBER']), 'body': notification},
            {'to': "120363377229741364@g.us", 'body': notification}
        ])
    
    return responses

async def process_internal_group_message(message: Dict, text_body: str) -> Dict:
    """Process messages from internal group"""
    bot_mention = "@916303689715"
    response = None
    
    if text_body == f"{bot_mention} start":
        settings['bot_active'] = True
        response = "Application started successfully."
    elif text_body == f"{bot_mention} shutdown":
        settings['bot_active'] = False
        response = "Application shut down successfully."
    elif text_body == f"{bot_mention} hotel number":
        response = f"Current hotel employee number: {settings['ALLOWED_HOTEL_EMPLOYEE_NUMBER']}"
    elif text_body == f"{bot_mention} airlines number":
        response = f"Current airlines number: {settings['ALLOWED_DUTY_MANAGER_NUMBER']}"
    elif text_body == f"{bot_mention} view rooms":
        response = f"Available rooms: {settings['ROOMS']}"
    elif text_body.startswith(f"{bot_mention} change"):
        # Handle all change commands
        cmd = text_body.replace(f"{bot_mention} change", "").strip()
        for key, pattern in {
            'ALLOWED_HOTEL_EMPLOYEE_NUMBER': 'hotel number',
            'ALLOWED_DUTY_MANAGER_NUMBER': 'airlines number',
            'ROOMS': 'rooms'
        }.items():
            if cmd.startswith(pattern):
                new_value = cmd.replace(pattern, "").strip()
                if new_value:
                    settings[key] = new_value
                    response = f"Updated {pattern} to: {new_value}"
                    break
    
    return {'to': message.get('chat_id'), 'body': response} if response else None

@app.post("/hook/messages/messages")
async def handle_new_messages(request_data: Dict[str, Any]):
    start_time = time.perf_counter()
    
    if not request_data or not (messages := request_data.get('messages', [])):
        raise HTTPException(status_code=400, detail="Invalid request data")
    
    current_ts = int(time.time())
    responses_to_send = []
    
    async def process_message(message: Dict) -> List[Dict]:
        if not (message_id := message.get("id")) or message_id in responded_messages:
            return []
        
        responded_messages.add(message_id)
        
        if not (chat_name := message.get("chat_name")):
            return []
        
        if not (text_body := (message.get("text", {}).get("body", "")).strip().lower()):
            return []
            
        if (current_ts - message.get("timestamp", 0)) > settings['MAX_DELAY']:
            return []
        
        if chat_name == "SIT - SIA Flight Delay Group Chat" and settings['bot_active']:
            if message.get("from") == settings['ALLOWED_DUTY_MANAGER_NUMBER']:
                return await process_flight_delay_message(message, text_body, current_ts)
        
        elif chat_name == "SIT - SIA Internal Group":
            if response := await process_internal_group_message(message, text_body):
                return [response]
        
        return []
    
    # Process all messages concurrently
    message_responses = await asyncio.gather(*[process_message(msg) for msg in messages])
    responses_to_send = [resp for sublist in message_responses for resp in sublist]
    
    # Send all responses in one batch
    if responses_to_send:
        await send_whapi_request(responses_to_send)
    
    elapsed = time.perf_counter() - start_time
    return JSONResponse({
        "status": "success",
        "time_taken": f"{elapsed:.4f} seconds"
    }, status_code=200)

# Simplified endpoint handlers
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
async def index():
    return "Bot is running"

@app.on_event("shutdown")
async def shutdown_event():
    await http_client.aclose()



