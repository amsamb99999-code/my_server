# -----------------------------------------------------------------------------
# bot.py - الملف الرئيسي لبوت الصقر (Falcon Bot)
# -----------------------------------------------------------------------------

import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# إعداد تسجيل الأنشطة (مهم جدًا لمراقبة البوت على Render)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# هذه الدالة سيتم استدعاؤها عندما يرسل المستخدم أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ترسل رسالة ترحيبية عند إرسال الأمر /start."""
    user = update.effective_user
    # رسالة الترحيب باللغة العربية
    welcome_message = (
        f"أهلاً بك يا {user.mention_html()}!\n\n"
        "أنا **بوت الصقر**، مساعدك الآلي لرصد فرص التداول في بينانس.\n\n"
        "أنا حاليًا في المرحلة الأولى من التطوير. جرب الأمر التالي لترى أنني أعمل:\n"
        "/ping"
    )
    await update.message.reply_html(welcome_message)


# هذه الدالة سيتم استدعاؤها عندما يرسل المستخدم أمر /ping
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ترد على المستخدم لتأكيد أن البوت يعمل."""
    await update.message.reply_text("أنا على قيد الحياة وأعمل بشكل سليم! 🚀")


def main() -> None:
    """الدالة الرئيسية لتشغيل البوت."""
    # نحصل على مفتاح بوت تليجرام من متغيرات البيئة (هذا آمن للنشر)
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
    if not TELEGRAM_TOKEN:
        logger.error("خطأ: لم يتم العثور على مفتاح بوت تليجرام (TELEGRAM_TOKEN).")
        return

    # إنشاء كائن التطبيق وربطه بمفتاح البوت
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # تسجيل الأوامر التي سيفهمها البوت
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ping", ping))

    # بدء تشغيل البوت (سيبقى يعمل ويستمع للأوامر)
    logger.info("تم بدء تشغيل البوت...")
    application.run_polling()


if __name__ == "__main__":
    main()


