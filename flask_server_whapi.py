from flask import Flask, request, jsonify
import requests
import re
from requests_toolbelt.multipart.encoder import MultipartEncoder
import os
from dotenv import load_dotenv
import logging
import time
from datetime import datetime
# Load environment variables from .env file
load_dotenv()

# Define constants
ALLOWED_DUTY_MANAGER_NUMBER = os.getenv('ALLOWED_DUTY_MANAGER_NUMBER')  # The specific number to process
MAX_DELAY = int(os.getenv('MAX_DELAY')) # Maximum allowed delay in seconds
bot = os.getenv('bot')
responded_messages = set()  # Track responded message IDs
alert_messages = []
ALLOWED_HOTEL_EMPLOYEE_NUMBER = 919100196360

# Set up logging
logging.basicConfig(level=logging.INFO)

# Initialize Flask app
app = Flask(__name__)

COMMANDS = {
    'TEXT': 'Simple text message',
    'IMAGE': 'Send image',
    'DOCUMENT': 'Send document',
    'VIDEO': 'Send video',
    'CONTACT': 'Send contact',
    'PRODUCT': 'Send product',
    'GROUP_CREATE': 'Create group',
    'GROUP_TEXT': 'Simple text message for the group',
    'GROUPS_IDS': "Get the id's of your three groups"
}

FILES = {
    'IMAGE': './files/file_example_JPG_100kB.jpg',
    'DOCUMENT': './files/file-example_PDF_500_kB.pdf',
    'VIDEO': './files/file_example_MP4_480_1_5MG.mp4',
    'VCARD': './files/sample-vcard.txt'
}

def extract_rooms(message):
    # Regex pattern to match number of rooms and type (including 'rms' as abbreviation for 'rooms')
    room_pattern = re.compile(r"(\d+)\s(?:ROOMS?|RMS?)\s*\((ECONOMY|BUSINESS)\)|(\d+)\s(?:ROOMS?|RMS?)\s(for\s(economy|business))?", re.IGNORECASE)
    
    room_matches = room_pattern.findall(message)
    result = []
    for match in room_matches:
        if match[0] and match[1]:  # Format like "7 ROOMS (ECONOMY)"
            result.append({'count': int(match[0]), 'type': match[1].upper()})
        elif match[2]:  # Format like "2 rms for economy"
            room_type = match[4].upper() if match[4] else "UNKNOWN"
            result.append({'count': int(match[2]), 'type': room_type})

    return result


def send_whapi_request(endpoint, params=None, method='POST'):
    headers = {
        'Authorization': f"Bearer {os.getenv('TOKEN')}"
    }
    url = f"{os.getenv('API_URL')}/{endpoint}"
    try:
        logging.info(f"Request to {url} with params: {params}")
        if params:
            if 'media' in params:
                details = params.pop('media').split(';')
                with open(details[0], 'rb') as file:
                    m = MultipartEncoder(fields={**params, 'media': (details[0], file, details[1])})
                    headers['Content-Type'] = m.content_type
                    response = requests.request(method, url, data=m, headers=headers)
            elif method == 'GET':
                response = requests.get(url, params=params, headers=headers)
            else:
                headers['Content-Type'] = 'application/json'
                response = requests.request(method, url, json=params, headers=headers)
        else:
            response = requests.request(method, url, headers=headers)
        
        logging.info(f"API Response: {response.json()}")
        return response.json()

    except Exception as e:
        logging.error(f"Error in send_whapi_request: {e}")
        return {'error': str(e)}

def set_hook():
    if os.getenv('BOT_URL'):
        settings = {
            'webhooks': [
                {
                    'url': f"{os.getenv('BOT_URL')}/hook/messages",
                    'events': [
                        {'type': "messages", 'method': "post"},
                        {'type': "chats", 'method': "patch"},
                        {'type': "statuses", 'method': "put"}
                    ],
                    'mode': "method"
                }
            ]
        }
        response = send_whapi_request('settings', settings, 'PATCH')
        logging.info(f"Webhook registration response: {response}")



@app.route('/hook/messages/messages', methods=['POST'])
def handle_new_messages():
    global bot
    global MAX_DELAY
    global ALLOWED_DUTY_MANAGER_NUMBER
    global ALLOWED_HOTEL_EMPLOYEE_NUMBER
    global responded_messages
    global alert_messages

    try:
        # Parse incoming JSON payload
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON payload received"}), 400

        # Log incoming data
        logging.info(f"Incoming data: {data}")

        messages = data.get('messages', [])
        if not messages:
            return jsonify({"error": "No messages found in the payload"}), 400

        # Get the current timestamp
        current_timestamp = int(time.time())

        for message in messages:
            message_id = message.get("id") 

            # Skip already responded messages
            if message_id in responded_messages:
                logging.info(f"Skipping already responded message ID: {message_id}")
                continue

            # Add to responded_messages early to avoid duplicate responses
            responded_messages.add(message_id)

            chat_name = message.get("chat_name")
            if not chat_name:
                logging.info("Message does not contain 'chat_name'. Skipping.")
                continue

            # Get message details
            text_body = message.get("text", {}).get("body", "").strip().lower()
            sender = message.get("from")
            timestamp = message.get("timestamp", 0)
            message_age = current_timestamp - timestamp

            if message_age > int(MAX_DELAY):
                logging.info(f"Skipping old message: {text_body} (Age: {message_age}s)")
                continue

            response_body = None

            if chat_name == "SIT - SIA Internal Group":
                if text_body == "@916303689715 start":
                    bot = True
                    response_body = "Application started successfully."
                elif text_body == "@916303689715 shutdown":
                    bot = False
                    response_body = "Application shut down successfully."
                elif text_body == "@916303689715 hotel employee number":
                    response_body = f"The current hotel employee number is {ALLOWED_HOTEL_EMPLOYEE_NUMBER}."
                elif text_body.startswith("@916303689715 change hotel employee number"):
                    new_number = text_body.replace("@916303689715 change hotel employee number", "").strip()
                    if new_number:
                        ALLOWED_HOTEL_EMPLOYEE_NUMBER = new_number
                        response_body = f"Hotel employee number updated to {new_number}."
                    else:
                        response_body = "Invalid number provided for 'Change Hotel Employee Number' command."
                elif text_body == "@916303689715 airlines number":
                    response_body = f"The current airlines number is {ALLOWED_DUTY_MANAGER_NUMBER}."
                elif text_body.startswith("@916303689715 change airlines number"):
                    new_number = text_body.replace("@916303689715 change airlines number", "").strip()
                    if new_number:
                        ALLOWED_DUTY_MANAGER_NUMBER = new_number
                        response_body = f"Airlines number updated to {new_number}."
                    else:
                        response_body = "Invalid number provided for 'Change Airlines Number' command."
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

            elif chat_name == "SIT - SIA Flight Delay Group Chat" and bot:
                if sender != ALLOWED_DUTY_MANAGER_NUMBER:
                    logging.info(f"Skipping unauthorized message from {sender}")
                    continue

                print("Text body",text_body)

                if "hi all" in text_body:
                    rooms = extract_rooms(text_body)
                    if len(rooms)>0:
                        if rooms[0]['count']<50: 
                            response_body = "RPS can"
                            alert_messages.append(text_body)
                        
                
                if "rps" in text_body and "we will take" in text_body:
                    print("Sending Response to hotel manager and internal group")
                    
                    stamp = message.get("timestamp")
                    readable_time = datetime.fromtimestamp(stamp)
                    response_body = f"We won a bid @{ALLOWED_HOTEL_EMPLOYEE_NUMBER} \n Alert recived on {readable_time} \n {alert_messages[-1:][0]} \n Confirmation {text_body}"

                    # print("messages : ", messages ,"\n")
                    endpoint = "messages/text"  # Example endpoint for sending text messages
                    response_payload = {'to': str(ALLOWED_HOTEL_EMPLOYEE_NUMBER), 'body': response_body}
                    response = send_whapi_request(endpoint, response_payload)

                    print("RESponse",response)
                    response_payload = {'to': "120363377229741364@g.us", 'body': response_body}
                    send_whapi_request('messages/text', response_payload)
                    logging.info(f"Responded to message ID: {message_id} with: {response_body}")

                    return jsonify({"status": "success"}), 200

            if response_body:
                # Send response
                response_payload = {'to': message.get('chat_id'), 'body': response_body}
                send_whapi_request('messages/text', response_payload)
                logging.info(f"Responded to message ID: {message_id} with: {response_body}")

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logging.error(f"Error in handle_new_messages: {e}")
        return jsonify({"error": str(e)}), 500

   

@app.route('/hook/messages/chats', methods=['PATCH'])
def handle_chats():
    try:
        data = request.json
        logging.info(f"Received chats webhook: {data}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logging.error(f"Error in handle_chats: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/hook/messages/groups', methods=['PUT'])
def handle_groups():
    try:
        data = request.json
        logging.info(f"Received chats webhook: {data}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logging.error(f"Error in handle_chats: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/hook/messages/statuses', methods=['PUT'])
def handle_statuses():
    try:
        data = request.json
        logging.info(f"Received statuses webhook: {data}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logging.error(f"Error in handle_statuses: {e}")
        return jsonify({"error": str(e)}), 500

# Debugging
# @app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
# def catch_all(path):
#     logging.warning(f"Unhandled request to /{path} with data: {request.json}")
#     return jsonify({"error": "Endpoint not found"}), 404


@app.route('/', methods=['GET'])
def index():
    return 'Bot is running'


if __name__ == '__main__':
    # Set webhook
    set_hook()
    # Start Flask app
    port = int(os.getenv('PORT', 8080))
    app.run(port=port, debug=True)