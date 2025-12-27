from flask import Flask, jsonify
from binance.client import Client
import pandas as pd
import ta
import os
import time
import requests

app = Flask(__name__)

api_key = os.environ.get('BINANCE_API_KEY')
api_secret = os.environ.get('BINANCE_API_SECRET')
telegram_token = os.environ.get('TELEGRAM_BOT_TOKEN')
telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')

client = Client(api_key, api_secret)

def send_telegram_message(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message
    }
    try:
        response = requests.post(url, data=data)
        return response.json()
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return None

@app.route('/')
def home():
    return jsonify({"message": "Telegram Binance Scanner is running."})

@app.route('/check_price')
def check_price():
    try:
        ticker = client.get_symbol_ticker(symbol="BTCUSDT")
        price = float(ticker['price'])
        threshold = 30000
        if price > threshold:
            send_telegram_message(telegram_token, telegram_chat_id, f"BTC price alert! Current price: {price}")
            return jsonify({"alert": f"Price is above {threshold}", "price": price})
        else:
            return jsonify({"alert": "Price below threshold", "price": price})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
