from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from config import BOT_TOKEN

async def get_photo_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_id = update.message.photo[-1].file_id
    print("\n" + "="*30)
    print("КОПИРУЙ ЭТОТ КОД (БЕЗ КАВЫЧЕК):")
    print(file_id)
    print("="*30 + "\n")
    await update.message.reply_text(f"Код выведен в терминал! Смотри черное окно.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    print("🤖 Бот запущен для получения ID. Скинь ему картинку!")
    app.add_handler(MessageHandler(filters.PHOTO, get_photo_id))
    app.run_polling()

if __name__ == "__main__":
    main()