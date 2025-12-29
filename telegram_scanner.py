import os
import time
import requests
from binance.client import Client

# --- Configuration ---
# Get environment variables with a check for None
# We use a placeholder string for missing values to prevent the script from crashing immediately
# and to provide a clear error message in the logs.
api_key = os.environ.get('BINANCE_API_KEY', 'MISSING_API_KEY')
api_secret = os.environ.get('BINANCE_API_SECRET', 'MISSING_API_SECRET')
telegram_token = os.environ.get('TELEGRAM_BOT_TOKEN', 'MISSING_TELEGRAM_TOKEN')
telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID', 'MISSING_CHAT_ID')

SYMBOL = "BTCUSDT"
THRESHOLD = 30000.0

def send_telegram_message(token, chat_id, message):
    """Sends a message to a specified Telegram chat."""
    # Check if the token is actually set before attempting to send
    if token == 'MISSING_TELEGRAM_TOKEN' or chat_id == 'MISSING_CHAT_ID':
        print("ERROR: Cannot send Telegram message. TELEGRAM_BOT_TOKEN or CHAT_ID is missing.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message
    }
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        print(f"Telegram message sent successfully. Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending Telegram message: {e}")

def check_price_and_alert():
    """Fetches the price and sends an alert if the threshold is exceeded."""
    print(f"Starting price check for {SYMBOL}...")
    
    # 1. Check for missing API keys before initializing Binance Client
    if api_key == 'MISSING_API_KEY' or api_secret == 'MISSING_API_SECRET':
        error_msg = "FATAL ERROR: Binance API keys are missing. Please set BINANCE_API_KEY and BINANCE_API_SECRET in Render Environment."
        print(error_msg)
        send_telegram_message(telegram_token, telegram_chat_id, error_msg)
        return

    # 2. Initialize Binance Client
    try:
        client = Client(api_key, api_secret)
    except Exception as e:
        error_msg = f"Error initializing Binance Client: {e}"
        print(error_msg)
        send_telegram_message(telegram_token, telegram_chat_id, error_msg)
        return

    # 3. Get the price
    try:
        ticker = client.get_symbol_ticker(symbol=SYMBOL)
        price = float(ticker['price'])
        
        print(f"Current {SYMBOL} price: {price}")

        # 4. Check the threshold
        if price > THRESHOLD:
            alert_message = f"ðŸš¨ BTC Price Alert! ðŸš¨\n\nPrice has exceeded the threshold of ${THRESHOLD:,.2f}.\nCurrent Price: ${price:,.2f}"
            send_telegram_message(telegram_token, telegram_chat_id, alert_message)
            print("Alert sent.")
        else:
            print(f"Price ${price:,.2f} is below the threshold ${THRESHOLD:,.2f}. No alert sent.")

    except Exception as e:
        error_message = f"An error occurred during the price check: {e}"
        print(error_message)
        send_telegram_message(telegram_token, telegram_chat_id, f"ERROR in Binance Scanner: {e}")

if __name__ == "__main__":
    check_price_and_alert()
