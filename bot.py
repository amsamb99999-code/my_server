# -----------------------------------------------------------------------------
# bot.py - بوت الصقر (النسخة النهائية المستقرة بدون pandas-ta)
# -----------------------------------------------------------------------------

import os
import logging
import asyncio
import pandas as pd
import numpy as np  # <-- سنستخدم numpy للحسابات
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from binance.client import Client
from binance.exceptions import BinanceAPIException

# --- إعدادات ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- متغيرات البيئة والمفاتيح ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.environ.get("BINANCE_SECRET_KEY")

# --- إعدادات الاستراتيجية ---
RSI_PERIOD = 14
RSI_OVERSOLD = 30
TIMEFRAME = Client.KLINE_INTERVAL_15MINUTE
SCAN_INTERVAL_SECONDS = 15 * 60

# --- الاتصال بالخدمات ---
try:
    bot = Bot(token=TELEGRAM_TOKEN)
    binance_client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)
    logger.info("تم الاتصال بنجاح بتليجرام وبينانس.")
except Exception as e:
    logger.critical(f"فشل الاتصال الأولي بالخدمات: {e}")
    exit()

# --- دوال الاستراتيجية والتحليل ---

def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    دالة مخصصة لحساب مؤشر القوة النسبية (RSI) بدون الاعتماد على مكتبات خارجية.
    """
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def get_top_usdt_pairs(limit=100):
    """تجلب قائمة بأفضل عملات USDT من حيث حجم التداول."""
    try:
        all_tickers = binance_client.get_ticker()
        usdt_pairs = [
            t for t in all_tickers 
            if t['symbol'].endswith('USDT') and 'UP' not in t['symbol'] and 'DOWN' not in t['symbol']
        ]
        sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x['quoteVolume']), reverse=True)
        return [p['symbol'] for p in sorted_pairs[:limit]]
    except Exception as e:
        logger.error(f"فشل في جلب قائمة العملات: {e}")
        return []

def check_strategy(symbol: str) -> bool:
    """تطبق الاستراتيجية على عملة معينة."""
    try:
        klines = binance_client.get_klines(symbol=symbol, interval=TIMEFRAME, limit=RSI_PERIOD + 50) # طلب بيانات أكثر للحساب الدقيق
        if len(klines) < RSI_PERIOD + 2:
            return False

        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])
        df['close'] = pd.to_numeric(df['close'])
        df['open'] = pd.to_numeric(df['open'])

        # *** التغيير الرئيسي: استخدام دالتنا المخصصة ***
        df['RSI'] = calculate_rsi(df, RSI_PERIOD)
        
        last_candle = df.iloc[-1]
        prev_candle = df.iloc[-2]

        rsi_is_oversold = last_candle['RSI'] < RSI_OVERSOLD
        
        is_bullish_engulfing = (
            last_candle['close'] > last_candle['open'] and
            prev_candle['close'] < prev_candle['open'] and
            last_candle['close'] > prev_candle['open'] and
            last_candle['open'] < prev_candle['close']
        )

        if rsi_is_oversold and is_bullish_engulfing:
            logger.info(f"🎯 تم العثور على فرصة! العملة: {symbol}, RSI: {last_candle['RSI']:.2f}")
            return True

    except Exception as e:
        logger.error(f"خطأ غير متوقع أثناء فحص العملة {symbol}: {e}")
    
    return False

# --- المهمة الرئيسية للمسح الدوري ---
async def scan_market(context: ContextTypes.DEFAULT_TYPE):
    logger.info("--- بدء جولة فحص السوق ---")
    symbols_to_scan = get_top_usdt_pairs(limit=150)
    if not symbols_to_scan:
        logger.warning("لم يتم العثور على عملات لفحصها.")
        return

    found_signals = []
    for symbol in symbols_to_scan:
        if check_strategy(symbol):
            found_signals.append(symbol)
        await asyncio.sleep(0.2)

    if found_signals:
        message = "🚨 **إشارة شراء قوية (RSI + ابتلاعية)** 🚨\n\n"
        for symbol in found_signals:
            binance_url = f"https://www.binance.com/en/trade/{symbol}"
            message += f"• <a href='{binance_url}'>{symbol}</a>\n"
        
        await context.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
    
    logger.info(f"--- انتهاء جولة الفحص. تم العثور على {len(found_signals)} إشارة. ---")

# --- دوال الأوامر للتحكم في البوت ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    welcome_message = (
        f"أهلاً بك يا {user.mention_html()}!\n\n"
        "أنا **بوت الصقر** (النسخة المستقرة).\n\n"
        "أقوم بفحص السوق كل 15 دقيقة. إذا لم تكن قد قمت بذلك، أرسل لي `Chat ID` الخاص بك: "
        f"`{update.effective_chat.id}`"
    )
    await update.message.reply_html(welcome_message)

def main() -> None:
    """الدالة الرئيسية لتشغيل البوت."""
    if not all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, BINANCE_API_KEY, BINANCE_SECRET_KEY]):
        logger.critical("أحد متغيرات البيئة المطلوبة مفقود.")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    job_queue = application.job_queue
    job_queue.run_repeating(scan_market, interval=SCAN_INTERVAL_SECONDS, first=10)

    logger.info("تم بدء تشغيل البوت (النسخة المستقرة) وجدولة مهمة فحص السوق...")
    application.run_polling()

if __name__ == "__main__":
    main()

