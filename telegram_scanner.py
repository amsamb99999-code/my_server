```python
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
    data = {"chat_id": chat_id, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"خطأ في إرسال رسالة تلغرام: {e}")

def get_klines_df(symbol, interval='5m', limit=50):
    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=[
        'Open time', 'Open', 'High', 'Low', 'Close', 'Volume',
        'Close time', 'Quote asset volume', 'Number of trades',
        'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'])
    df['Close'] = df['Close'].astype(float)
    return df

def calculate_indicators(df):
    df['ema_short'] = ta.trend.EMAIndicator(df['Close'], window=9).ema_indicator()
    df['ema_long'] = ta.trend.EMAIndicator(df['Close'], window=21).ema_indicator()
    df['rsi'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
    return df

def generate_signal(df):
    if len(df) < 2:
        return None
    prev_short = df['ema_short'].iloc[-2]
    prev_long = df['ema_long'].iloc[-2]
    curr_short = df['ema_short'].iloc[-1]
    curr_long = df['ema_long'].iloc[-1]
    rsi = df['rsi'].iloc[-1]

    if (prev_short <= prev_long) and (curr_short > curr_long) and (rsi < 30):
        return "شراء"
    elif (prev_short >= prev_long) and (curr_short < curr_long) and (rsi > 70):
        return "بيع"
    else:
        return None

@app.route('/signals')
def signals():
    symbols = [s['symbol'] for s in client.get_exchange_info()['symbols']
               if s['quoteAsset'] == 'USDT' and s['status'] == 'TRADING']
    signals_dict = {}
    for symbol in symbols:
        try:
            df = get_klines_df(symbol)
            df = calculate_indicators(df)
            signal = generate_signal(df)
            if signal:
                signals_dict[symbol] = signal
                # إرسال إشعار لتلجرام
                if telegram_token and telegram_chat_id:
                    message = f"إشارة {signal} لـ {symbol}"
                    send_telegram_message(telegram_token, telegram_chat_id, message)
        except Exception as e:
            print(f"خطأ في {symbol}: {e}")
        time.sleep(0.3)
    return jsonify(signals_dict)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```
