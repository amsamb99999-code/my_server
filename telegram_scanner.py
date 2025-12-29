# -----------------------------------------------------------------------------
# bot.py - بوت الصقر (Falcon Bot) - النسخة الاحترافية المتكاملة
# -----------------------------------------------------------------------------

import os
import logging
import asyncio
import pandas as pd
import pandas_ta as ta
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
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") # <-- سنضيف هذا لاحقًا
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.environ.get("BINANCE_SECRET_KEY")

# --- إعدادات الاستراتيجية ---
RSI_PERIOD = 14
RSI_OVERSOLD = 30
TIMEFRAME = Client.KLINE_INTERVAL_15MINUTE # الإطار الزمني: 15 دقيقة
SCAN_INTERVAL_SECONDS = 15 * 60 # الفاصل الزمني للمسح: 15 دقيقة

# --- الاتصال بالخدمات ---
try:
    bot = Bot(token=TELEGRAM_TOKEN)
    binance_client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)
    logger.info("تم الاتصال بنجاح بتليجرام وبينانس.")
except Exception as e:
    logger.critical(f"فشل الاتصال الأولي بالخدمات: {e}")
    # في حالة فشل الاتصال الأولي، لا فائدة من المتابعة
    exit()

# --- دوال الاستراتيجية والتحليل ---

def get_top_usdt_pairs(limit=100):
    """تجلب قائمة بأفضل عملات USDT من حيث حجم التداول."""
    try:
        all_tickers = binance_client.get_ticker()
        usdt_pairs = [
            t for t in all_tickers 
            if t['symbol'].endswith('USDT') and not t['symbol'].endswith('UPUSDT') and not t['symbol'].endswith('DOWNUSDT')
        ]
        # فرز العملات حسب حجم التداول (quoteVolume)
        sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x['quoteVolume']), reverse=True)
        return [p['symbol'] for p in sorted_pairs[:limit]]
    except Exception as e:
        logger.error(f"فشل في جلب قائمة العملات: {e}")
        return []

def check_strategy(symbol: str) -> bool:
    """تطبق الاستراتيجية على عملة معينة."""
    try:
        # 1. جلب بيانات الشموع (الشموع التاريخية)
        klines = binance_client.get_klines(symbol=symbol, interval=TIMEFRAME, limit=RSI_PERIOD + 5)
        if len(klines) < RSI_PERIOD + 2:
            return False # لا توجد بيانات كافية

        # 2. تحويل البيانات إلى DataFrame باستخدام Pandas
        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])
        df['close'] = pd.to_numeric(df['close'])
        df['open'] = pd.to_numeric(df['open'])

        # 3. حساب مؤشر RSI
        df.ta.rsi(length=RSI_PERIOD, append=True)
        
        # 4. استخلاص آخر شمعتين وبيانات RSI الخاصة بهما
        last_candle = df.iloc[-1]
        prev_candle = df.iloc[-2]

        # 5. تطبيق شروط الاستراتيجية
        # الشرط الأول: هل مؤشر RSI في منطقة ذروة البيع؟
        rsi_is_oversold = last_candle[f'RSI_{RSI_PERIOD}'] < RSI_OVERSOLD
        
        # الشرط الثاني: هل الشمعة الأخيرة ابتلاعية صاعدة؟
        # (إغلاقها أعلى من افتتاحها، وجسمها يبتلع جسم الشمعة السابقة الهابطة)
        is_bullish_engulfing = (
            last_candle['close'] > last_candle['open'] and    # شمعة صاعدة
            prev_candle['close'] < prev_candle['open'] and    # شمعة سابقة هابطة
            last_candle['close'] > prev_candle['open'] and    # إغلاق الحالية أعلى من افتتاح السابقة
            last_candle['open'] < prev_candle['close']        # افتتاح الحالية أدنى من إغلاق السابقة
        )

        if rsi_is_oversold and is_bullish_engulfing:
            logger.info(f"🎯 تم العثور على فرصة! العملة: {symbol}, RSI: {last_candle[f'RSI_{RSI_PERIOD}']:.2f}")
            return True

    except BinanceAPIException as e:
        if e.code == -1121: # رمز خطأ "عملة غير صالحة"
            pass # تجاهل العملات غير الصالحة بصمت
        else:
            logger.warning(f"تحذير واجهة بينانس للعملة {symbol}: {e}")
    except Exception as e:
        logger.error(f"خطأ غير متوقع أثناء فحص العملة {symbol}: {e}")
    
    return False

# --- المهمة الرئيسية للمسح الدوري ---

async def scan_market(context: ContextTypes.DEFAULT_TYPE):
    """تقوم بمسح السوق بشكل دوري وإرسال الإشعارات."""
    logger.info("--- بدء جولة فحص السوق ---")
    
    # جلب قائمة العملات المراد فحصها
    symbols_to_scan = get_top_usdt_pairs(limit=150) # فحص أفضل 150 عملة
    if not symbols_to_scan:
        logger.warning("لم يتم العثور على عملات لفحصها. تخطي هذه الجولة.")
        return

    found_signals = []
    for symbol in symbols_to_scan:
        if check_strategy(symbol):
            found_signals.append(symbol)
        await asyncio.sleep(0.2) # فاصل بسيط بين كل طلب لتجنب إغراق واجهة API

    if found_signals:
        message = "🚨 **إشارة شراء قوية (RSI + ابتلاعية)** 🚨\n\n"
        for symbol in found_signals:
            binance_url = f"https://www.binance.com/en/trade/{symbol}"
            message += f"• <a href='{binance_url}'>{symbol}</a>\n"
        
        # إرسال الرسالة إلى حسابك الخاص على تليجرام
        await context.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
    
    logger.info(f"--- انتهاء جولة الفحص. تم العثور على {len(found_signals)} إشارة. ---")


# --- دوال الأوامر للتحكم في البوت ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يرسل رسالة ترحيبية ويشرح كيفية الحصول على Chat ID."""
    user = update.effective_user
    welcome_message = (
        f"أهلاً بك يا {user.mention_html()}!\n\n"
        "أنا **بوت الصقر** (النسخة الاحترافية).\n\n"
        "أقوم بفحص السوق كل 15 دقيقة بحثًا عن فرص شراء قوية.\n\n"
        "لأتمكن من إرسال الإشعارات لك، أحتاج إلى معرفة `Chat ID` الخاص بك. "
        f"الـ `Chat ID` الخاص بك هو: `{update.effective_chat.id}`\n\n"
        "**الرجاء نسخ هذا الرقم وإضافته كمتغير بيئة جديد في Render باسم `TELEGRAM_CHAT_ID`**."
    )
    await update.message.reply_html(welcome_message)


def main() -> None:
    """الدالة الرئيسية لتشغيل البوت وإعداد المهام المجدولة."""
    if not all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, BINANCE_API_KEY, BINANCE_SECRET_KEY]):
        logger.critical("أحد متغيرات البيئة المطلوبة مفقود. تأكد من إعداد TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, BINANCE_API_KEY, BINANCE_SECRET_KEY.")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # إضافة معالج الأوامر
    application.add_handler(CommandHandler("start", start))

    # إعداد وتشغيل المهمة المجدولة
    job_queue = application.job_queue
    job_queue.run_repeating(scan_market, interval=SCAN_INTERVAL_SECONDS, first=10) # ابدأ بعد 10 ثوانٍ

    logger.info("تم بدء تشغيل البوت الاحترافي وجدولة مهمة فحص السوق...")
    application.run_polling()


if __name__ == "__main__":
    main()


