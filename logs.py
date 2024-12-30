import logging
from flask import Flask, request, jsonify
import watchtower

# Create Flask app instance
app = Flask(__name__)

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

@app.route('/bot', methods=['POST'])
def bot():
    data = request.json
    user_message = data.get('message', '').lower()
    logger.info(f"Received message: {user_message}")  # Log incoming message to CloudWatch

    # Respond to "hello" message
    if user_message == "hello":
        response = {"response": "Hi there! How can I assist you today?"}
        logger.info("Responded with greeting Hi there! How can I assist you today? IT worked.")  # Log the response
    else:
        response = {"response": "Sorry, I can only respond to 'hello' right now."}
        logger.warning(f"Unsupported message: {user_message}")  # Log warning for unsupported messages

    return jsonify(response)

@app.route('/')
def index():
    logger.info("Flask app is running!")  # Log when the homepage is accessed
    return "Flask Bot is Running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)