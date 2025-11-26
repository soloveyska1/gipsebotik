"""
Скрипт для загрузки фото и получения file_id.
Запусти один раз, отправь боту картинку, получи file_id.
"""
import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from config import BOT_TOKEN

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фото — выводит file_id."""
    if update.message.photo:
        photo = update.message.photo[-1]  # Самое большое разрешение
        file_id = photo.file_id
        print(f"\n{'='*50}")
        print(f"FILE_ID для картинки:")
        print(f"{'='*50}")
        print(file_id)
        print(f"{'='*50}\n")

        await update.message.reply_text(
            f"✅ Получен file_id:\n\n<code>{file_id}</code>\n\n"
            "Скопируй его и вставь в handlers/client.py в переменную SALON_CODE_PHOTO_ID",
            parse_mode="HTML"
        )

def main():
    print("🤖 Бот запущен. Отправь ему картинку для получения file_id...")
    print("Нажми Ctrl+C для выхода\n")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.run_polling()

if __name__ == "__main__":
    main()
