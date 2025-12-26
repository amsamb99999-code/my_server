import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException
from tabulate import tabulate
from telegram import Bot
import os
import time
import asyncio

# =================================================================
# 1. إعدادات API و Telegram (يجب تعيينها كمتغيرات بيئة على Railway)
# =================================================================
# مفاتيح Binance API
API_KEY = os.environ.get('BINANCE_API_KEY', '')
API_SECRET = os.environ.get('BINANCE_API_SECRET', '')

# إعدادات Telegram
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', 'YOUR_CHAT_ID') # يمكن أن يكون ID قناة أو مجموعة أو مستخدم

# =================================================================
# 2. إعدادات التداول الافتراضية
# =================================================================
INTERVAL = Client.KLINE_INTERVAL_4HOUR  # إطار زمني 4 ساعات
LIMIT = 100  # عدد الشموع التاريخية المراد جلبها
BB_PERIOD = 20 # فترة مؤشر بولينجر باندز
VOLUME_CONFIRMATION_FACTOR = 1.5 # عامل تأكيد الحجم
SCAN_INTERVAL_SECONDS = 4 * 60 * 60 # المسح كل 4 ساعات (4 ساعات * 60 دقيقة * 60 ثانية)

# =================================================================
# 3. دالة إرسال الرسائل إلى تليجرام
# =================================================================
async def send_telegram_message(message):
    """
    إرسال رسالة إلى تليجرام باستخدام البوت.
    """
    if TELEGRAM_BOT_TOKEN == 'YOUR_BOT_TOKEN' or TELEGRAM_CHAT_ID == 'YOUR_CHAT_ID':
        print("تحذير: لم يتم تعيين رمز البوت أو معرف الدردشة. لن يتم إرسال الرسالة إلى تليجرام.")
        return

    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
        print("تم إرسال التقرير إلى تليجرام بنجاح.")
    except Exception as e:
        print(f"خطأ في إرسال رسالة تليجرام: {e}")

# =================================================================
# 4. دالة جلب قائمة العملات (بدون تغيير)
# =================================================================
def get_usdt_symbols(client):
    """
    جلب قائمة بجميع أزواج التداول التي تنتهي بـ USDT.
    """
    try:
        print("جلب قائمة أزواج التداول (USDT)...")
        exchange_info = client.get_exchange_info()
        symbols = [
            s['symbol'] for s in exchange_info['symbols'] 
            if s['symbol'].endswith('USDT') and s['status'] == 'TRADING'
        ]
        return symbols[:100] 
    except BinanceAPIException as e:
        print(f"خطأ في الاتصال بـ Binance API أثناء جلب الرموز: {e}")
        return []
    except Exception as e:
        print(f"حدث خطأ غير متوقع أثناء جلب الرموز: {e}")
        return []

# =================================================================
# 5. دالة جلب البيانات (بدون تغيير)
# =================================================================
def get_historical_data(client, symbol, interval, limit):
    """
    يتصل بـ Binance API لجلب بيانات الشموع التاريخية (OHLCV)
    ويحولها إلى إطار بيانات (DataFrame) من Pandas.
    """
    try:
        klines = client.get_historical_klines(symbol, interval, limit=limit)
        
        if not klines or len(klines) < limit:
            return None

        data = pd.DataFrame(klines, columns=[
            'Open Time', 'Open', 'High', 'Low', 'Close', 'Volume', 
            'Close Time', 'Quote Asset Volume', 'Number of Trades', 
            'Taker Buy Base Asset Volume', 'Taker Buy Quote Asset Volume', 'Ignore'
        ])
        
        data['Open Time'] = pd.to_datetime(data['Open Time'], unit='ms')
        numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        data[numeric_cols] = data[numeric_cols].apply(pd.to_numeric)
        data.set_index('Open Time', inplace=True)
        
        return data[['Open', 'High', 'Low', 'Close', 'Volume']]
    except BinanceAPIException as e:
        return None
    except Exception as e:
        return None

# =================================================================
# 6. دالة تطبيق الاستراتيجية (باستخدام بولينجر باندز) (بدون تغيير)
# =================================================================
def apply_breakout_strategy(df, symbol):
    """
    تطبيق منطق استراتيجية الاختراق باستخدام بولينجر باندز وتأكيد الحجم.
    """
    if df is None or len(df) < BB_PERIOD:
        return None 

    # 1. حساب مؤشر بولينجر باندز (Bollinger Bands)
    df['SMA'] = df['Close'].rolling(window=BB_PERIOD).mean()
    df['StdDev'] = df['Close'].rolling(window=BB_PERIOD).std()
    df['UpperBand'] = df['SMA'] + (df['StdDev'] * 2)
    df['LowerBand'] = df['SMA'] - (df['StdDev'] * 2)

    # 2. تحليل الشمعة الأخيرة (التي أغلقت)
    last_candle = df.iloc[-2] 
    
    current_close = last_candle['Close']
    current_volume = last_candle['Volume']
    
    upper_band = last_candle['UpperBand']
    lower_band = last_candle['LowerBand']
    
    # 3. تأكيد الحجم (Volume Confirmation)
    avg_volume = df['Volume'].iloc[-BB_PERIOD-2:-2].mean()
    volume_confirmed = current_volume > avg_volume * VOLUME_CONFIRMATION_FACTOR

    # 4. توليد الإشارات
    
    # إشارة شراء (اختراق الحد العلوي)
    if current_close > upper_band:
        if volume_confirmed:
            return {
                'Symbol': symbol,
                'Signal': 'شراء قوي (اختراق BB)',
                'Price': f"{current_close:.8f}",
                'Level': f"{upper_band:.8f}",
                'Volume Factor': f"{current_volume/avg_volume:.2f}x",
                'Timeframe': INTERVAL
            }
    
    # إشارة بيع (كسر الحد السفلي)
    elif current_close < lower_band:
        if volume_confirmed:
            return {
                'Symbol': symbol,
                'Signal': 'بيع قوي (كسر BB)',
                'Price': f"{current_close:.8f}",
                'Level': f"{lower_band:.8f}",
                'Volume Factor': f"{current_volume/avg_volume:.2f}x",
                'Timeframe': INTERVAL
            }
    
    return None 

# =================================================================
# 7. الدالة الرئيسية للمسح
# =================================================================
def scan_market():
    """
    تقوم بمسح السوق وتوليد تقرير الإشارات.
    """
    client = Client(API_KEY, API_SECRET)
    symbols_to_scan = get_usdt_symbols(client)
    
    if not symbols_to_scan:
        return "فشل في جلب قائمة العملات. يرجى التحقق من اتصالك بالإنترنت أو مفاتيح API."

    strong_signals = []
    
    print(f"بدء مسح {len(symbols_to_scan)} عملة على إطار {INTERVAL}...")
    
    for i, symbol in enumerate(symbols_to_scan):
        print(f"[{i+1}/{len(symbols_to_scan)}] تحليل {symbol}...", end='\r')
        
        df = get_historical_data(client, symbol, INTERVAL, LIMIT)
        signal = apply_breakout_strategy(df, symbol)
        
        if signal:
            strong_signals.append(signal)
            print(f"*** إشارة قوية لـ {symbol} ***")
        
        time.sleep(0.1) # تأخير بسيط

    # بناء التقرير
    report = f"*{time.strftime('%Y-%m-%d %H:%M:%S')} - تقرير ماسح بينانس (BB Breakout)*\n\n"
    
    if strong_signals:
        results_df = pd.DataFrame(strong_signals)
        # استخدام تنسيق Markdown للجدول
        report += tabulate(results_df, headers="keys", tablefmt="pipe", numalign="left")
    else:
        report += "لم يتم العثور على إشارات شراء أو بيع قوية في العملات التي تم مسحها."
        
    return report

# =================================================================
# 8. دالة التشغيل المستمر (الدالة التي ستعمل على Railway)
# =================================================================
async def main_loop():
    """
    الحلقة الرئيسية التي تعمل بشكل مستمر.
    """
    print("بدء حلقة التشغيل المستمر...")
    while True:
        try:
            report = scan_market()
            print("\n" + "="*50)
            print(report)
            print("="*50)
            
            # إرسال التقرير إلى تليجرام
            await send_telegram_message(report)
            
            print(f"الانتظار لمدة {SCAN_INTERVAL_SECONDS // 3600} ساعات قبل المسح التالي...")
            await asyncio.sleep(SCAN_INTERVAL_SECONDS)
            
        except Exception as e:
            error_message = f"خطأ فادح في حلقة التشغيل الرئيسية: {e}. إعادة المحاولة بعد 60 ثانية."
            print(error_message)
            await send_telegram_message(f"🚨 *خطأ في البوت:* {error_message}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    # تشغيل الحلقة الرئيسية
    asyncio.run(main_loop())
