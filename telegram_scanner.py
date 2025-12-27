mport os
import time
import asyncio
import threading
import pandas as pd
from flask import Flask
from binance.client import Client
from binance.exceptions import BinanceAPIException
from tabulate import tabulate
from telegram import Bot

# =================================================================
# 1. إعداد خادم ويب (Flask) لإرضاء نظام فحص المنافذ في Render
# =================================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and scanning!", 200

@app.route('/health')
def health():
    return "OK", 200

def run_web_server():
    # Render يمرر المنفذ عبر متغير البيئة PORT
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting web server on port {port}...")
    app.run(host='0.0.0.0', port=port)

# =================================================================
# 2. إعدادات البوت والمتغيرات
# =================================================================
API_KEY = os.environ.get('BINANCE_API_KEY', '')
API_SECRET = os.environ.get('BINANCE_API_SECRET', '')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

INTERVAL = Client.KLINE_INTERVAL_4HOUR
LIMIT = 100
BB_PERIOD = 20
VOLUME_FACTOR = 1.5
SCAN_INTERVAL = 4 * 60 * 60 # 4 ساعات

# =================================================================
# 3. منطق البوت (المسح والتحليل)
# =================================================================
async def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing!")
        return
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
    except Exception as e:
        print(f"Telegram Error: {e}")

def get_data(client, symbol):
    try:
        klines = client.get_historical_klines(symbol, INTERVAL, limit=LIMIT)
        if not klines or len(klines) < BB_PERIOD + 2:
            return None
        df = pd.DataFrame(klines, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume', 'CT', 'QV', 'NT', 'TB', 'TQ', 'I'])
        df[['Close', 'Volume']] = df[['Close', 'Volume']].apply(pd.to_numeric)
        return df[['Close', 'Volume']]
    except:
        return None

def analyze(df, symbol):
    df['SMA'] = df['Close'].rolling(window=BB_PERIOD).mean()
    df['Std'] = df['Close'].rolling(window=BB_PERIOD).std()
    df['Upper'] = df['SMA'] + (df['Std'] * 2)
    df['Lower'] = df['SMA'] - (df['Std'] * 2)
    
    last = df.iloc[-2] # الشمعة المكتملة الأخيرة
    prev_vols = df['Volume'].iloc[-BB_PERIOD-2:-2].mean()
    
    if last['Close'] > last['Upper'] and last['Volume'] > prev_vols * VOLUME_FACTOR:
        return {'Symbol': symbol, 'Signal': 'BUY 🚀', 'Price': last['Close']}
    elif last['Close'] < last['Lower'] and last['Volume'] > prev_vols * VOLUME_FACTOR:
        return {'Symbol': symbol, 'Signal': 'SELL 📉', 'Price': last['Close']}
    return None

async def main_bot_logic():
    print("Bot logic started...")
    client = Client(API_KEY, API_SECRET)
    
    while True:
        try:
            print("Starting new scan...")
            exchange_info = client.get_exchange_info()
            symbols = [s['symbol'] for s in exchange_info['symbols'] if s['symbol'].endswith('USDT') and s['status'] == 'TRADING'][:50] # تحديد العدد لتجنب الحظر
            
            signals = []
            for symbol in symbols:
                df = get_data(client, symbol)
                res = analyze(df, symbol) if df is not None else None
                if res:
                    signals.append(res)
                await asyncio.sleep(0.2) # تجنب Rate Limit
            
            report = f"🔍 *Scan Report ({time.strftime('%H:%M')})*\n"
            if signals:
                report += "```\n" + tabulate(pd.DataFrame(signals), headers='keys', tablefmt='simple') + "\n```"
            else:
                report += "No strong signals found."
            
            await send_telegram(report)
            print(f"Scan complete. Sleeping for {SCAN_INTERVAL/3600} hours...")
            await asyncio.sleep(SCAN_INTERVAL)
            
        except Exception as e:
            print(f"Main Loop Error: {e}")
            await asyncio.sleep(60)

# =================================================================
# 4. نقطة الانطلاق
# =================================================================
if __name__ == "__main__":
    # 1. تشغيل خادم الويب في خيط منفصل
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    # 2. تشغيل منطق البوت في الحلقة الرئيسية
    asyncio.run(main_bot_logic())
