import os
import time
import requests
from binance.client import Client

# --- Configuration ---
# Get environment variables
api_key = os.environ.get('BINANCE_API_KEY')
api_secret = os.environ.get('BINANCE_API_SECRET')
telegram_token = os.environ.get('TELEGRAM_BOT_TOKEN')
telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')
SYMBOL = "BTCUSDT"
THRESHOLD = 30000.0

# Initialize Binance Client
try:
    client = Client(api_key, api_secret)
except Exception as e:
    print(f"Error initializing Binance Client: {e}")
    # In a real-world scenario, you might want to exit here if the client fails to initialize
    # exit(1)

def send_telegram_message(token, chat_id, message):
    """Sends a message to a specified Telegram chat."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message
    }
    try:
        response = requests.post(url, data=data)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        print(f"Telegram message sent successfully. Response: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending Telegram message: {e}")

def check_price_and_alert():
    """Fetches the price and sends an alert if the threshold is exceeded."""
    print(f"Starting price check for {SYMBOL}...")
    
    # Check if all necessary tokens are available
    if not all([api_key, api_secret, telegram_token, telegram_chat_id]):
        print("ERROR: One or more environment variables (API keys/tokens) are missing.")
        send_telegram_message(telegram_token, telegram_chat_id, "ERROR: Binance Scanner failed to run due to missing configuration.")
        return

    try:
        # 1. Get the price
        ticker = client.get_symbol_ticker(symbol=SYMBOL)
        price = float(ticker['price'])
        
        print(f"Current {SYMBOL} price: {price}")

        # 2. Check the threshold
        if price > THRESHOLD:
            alert_message = f"ðŸš¨ BTC Price Alert! ðŸš¨\n\nPrice has exceeded the threshold of ${THRESHOLD:,.2f}.\nCurrent Price: ${price:,.2f}"
            send_telegram_message(telegram_token, telegram_chat_id, alert_message)
            print("Alert sent.")
        else:
            print(f"Price ${price:,.2f} is below the threshold ${THRESHOLD:,.2f}. No alert sent.")

    except Exception as e:
        error_message = f"An error occurred during the price check: {e}"
        print(error_message)
        # Optionally send an error alert to Telegram
        send_telegram_message(telegram_token, telegram_chat_id, f"ERROR in Binance Scanner: {e}")

if __name__ == "__main__":
    # The script runs the check once and then exits, which is perfect for a Cron Job.
    check_price_and_alert()
