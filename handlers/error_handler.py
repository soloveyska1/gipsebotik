"""
⚠️ ERROR HANDLER - Обработка ошибок
"""
import logging
import traceback
from html import escape
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config import LOG_CHANNEL_ID, ADMIN_IDS

logger = logging.getLogger(__name__)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный обработчик ошибок"""

    # Логируем ошибку
    logger.error(f"Exception while handling an update: {context.error}")

    # Получаем трейсбек
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = ''.join(tb_list)

    # Формируем сообщение об ошибке
    error_message = f"⚠️ <b>ОШИБКА В БОТЕ</b>\n\n"

    if update:
        if update.effective_user:
            error_message += f"👤 User: {update.effective_user.id}\n"
            error_message += f"📛 Name: {escape(update.effective_user.full_name or 'Unknown')}\n"

        if update.effective_chat:
            error_message += f"💬 Chat: {update.effective_chat.id}\n"

        if update.callback_query:
            error_message += f"🔘 Callback: {update.callback_query.data}\n"

        if update.message and update.message.text:
            error_message += f"💬 Text: {escape(update.message.text[:100])}\n"

    error_message += f"\n❌ <b>Error:</b>\n<code>{escape(str(context.error)[:500])}</code>\n"
    error_message += f"\n📜 <b>Traceback:</b>\n<code>{escape(tb_string[-1000:])}</code>"

    # Отправляем в канал логов
    if LOG_CHANNEL_ID:
        try:
            await context.bot.send_message(
                LOG_CHANNEL_ID,
                error_message[:4000],  # Telegram limit
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to send error to log channel: {e}")

    # Уведомляем админов
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"⚠️ Ошибка в боте!\n\n{str(context.error)[:200]}\n\nПодробности в логах.",
                parse_mode=ParseMode.HTML
            )
        except:
            pass

    # Отвечаем пользователю
    if update:
        try:
            if update.callback_query:
                await update.callback_query.answer("❌ Произошла ошибка. Попробуйте позже.")
            elif update.message:
                await update.message.reply_text(
                    "❌ Произошла ошибка. Попробуйте позже или обратитесь в поддержку.\n\n"
                    "/start — начать заново"
                )
        except:
            pass
