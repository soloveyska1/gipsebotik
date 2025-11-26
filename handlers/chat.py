"""
💬 CHAT SYSTEM - Чат между менеджером и клиентом
"""
import logging
from html import escape
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from config import ADMIN_IDS
from database import core as db

logger = logging.getLogger(__name__)

# States
CHAT_STEP = 200


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def chat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало чата по заказу"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    # Определяем order_id из callback
    data = query.data
    if data.startswith("adm_chat_"):
        order_id = int(data.replace("adm_chat_", ""))
    elif data.startswith("chat_order_"):
        order_id = int(data.replace("chat_order_", ""))
    else:
        await query.edit_message_text("❌ Ошибка: не найден ID заказа")
        return ConversationHandler.END

    order = await db.get_order(order_id)
    if not order:
        await query.edit_message_text("❌ Заказ не найден")
        return ConversationHandler.END

    # Проверяем доступ
    if not is_admin(user_id) and order['user_id'] != user_id:
        await query.edit_message_text("❌ У вас нет доступа к этому чату")
        return ConversationHandler.END

    context.user_data['chat_order_id'] = order_id
    context.user_data['chat_is_admin'] = is_admin(user_id)

    # Получаем историю чата
    messages = await db.get_chat_history(order_id)

    text = f"💬 <b>ЧАТ ПО ЗАКАЗУ #{order_id}</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    if messages:
        for msg in messages[-10:]:  # Последние 10 сообщений
            sender = "👑 Менеджер" if msg['is_admin'] else "👤 Клиент"
            content = escape((msg.get('content') or '')[:100])
            time = str(msg.get('created_at', ''))[-8:-3]

            text += f"<b>{sender}</b> <i>{time}</i>\n"
            text += f"{content}\n\n"
    else:
        text += "<i>Сообщений пока нет</i>\n\n"

    text += "━━━━━━━━━━━━━━━━━━━━\n"
    text += "📝 Отправьте сообщение, фото или файл"

    keyboard = [[InlineKeyboardButton("❌ Закрыть чат", callback_data="chat_close")]]

    if is_admin(user_id):
        keyboard.insert(0, [InlineKeyboardButton("◀️ К заказу", callback_data=f"adm_order_{order_id}")])
    else:
        keyboard.insert(0, [InlineKeyboardButton("◀️ К заказу", callback_data=f"my_order_{order_id}")])

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))

    return CHAT_STEP


async def chat_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений в чате"""
    user_id = update.effective_user.id
    order_id = context.user_data.get('chat_order_id')
    is_admin_user = context.user_data.get('chat_is_admin', False)

    if not order_id:
        await update.message.reply_text("❌ Ошибка: сессия чата потеряна. Начните заново.")
        return ConversationHandler.END

    order = await db.get_order(order_id)
    if not order:
        await update.message.reply_text("❌ Заказ не найден")
        return ConversationHandler.END

    # Определяем тип сообщения
    msg_type = 'text'
    content = ''
    file_id = None

    if update.message.text:
        msg_type = 'text'
        content = update.message.text
    elif update.message.photo:
        msg_type = 'photo'
        file_id = update.message.photo[-1].file_id
        content = update.message.caption or '[Фото]'
    elif update.message.document:
        msg_type = 'document'
        file_id = update.message.document.file_id
        content = update.message.caption or f'[Файл: {update.message.document.file_name}]'
    elif update.message.voice:
        msg_type = 'voice'
        file_id = update.message.voice.file_id
        content = '[Голосовое сообщение]'
    elif update.message.video_note:
        msg_type = 'video_note'
        file_id = update.message.video_note.file_id
        content = '[Видеосообщение]'

    # Сохраняем сообщение
    await db.add_chat_message(
        order_id,
        user_id,
        is_admin_user,
        msg_type,
        content,
        file_id
    )

    # Отправляем уведомление другой стороне
    if is_admin_user:
        # Уведомляем клиента
        client_id = order['user_id']
        try:
            notify_text = f"💬 <b>Новое сообщение по заказу #{order_id}</b>\n\n"
            notify_text += f"👑 <b>Менеджер:</b>\n{escape(content[:200])}"

            keyboard = [[InlineKeyboardButton("💬 Открыть чат", callback_data=f"chat_order_{order_id}")]]

            if file_id and msg_type == 'photo':
                await context.bot.send_photo(
                    client_id,
                    file_id,
                    caption=notify_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            elif file_id and msg_type == 'document':
                await context.bot.send_document(
                    client_id,
                    file_id,
                    caption=notify_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            elif file_id and msg_type == 'voice':
                await context.bot.send_voice(
                    client_id,
                    file_id,
                    caption=notify_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await context.bot.send_message(
                    client_id,
                    notify_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        except Exception as e:
            logger.warning(f"Не удалось уведомить клиента {client_id}: {e}")
    else:
        # Уведомляем админов
        for admin_id in ADMIN_IDS:
            try:
                user = await db.get_user(user_id)
                user_name = user.get('full_name', 'Клиент') if user else 'Клиент'

                notify_text = f"💬 <b>Сообщение от клиента</b>\n"
                notify_text += f"📦 Заказ #{order_id}\n"
                notify_text += f"👤 {escape(user_name)}\n\n"
                notify_text += f"{escape(content[:200])}"

                keyboard = [[InlineKeyboardButton("💬 Ответить", callback_data=f"adm_chat_{order_id}")]]

                if file_id and msg_type == 'photo':
                    await context.bot.send_photo(
                        admin_id,
                        file_id,
                        caption=notify_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                elif file_id and msg_type == 'document':
                    await context.bot.send_document(
                        admin_id,
                        file_id,
                        caption=notify_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                elif file_id and msg_type == 'voice':
                    await context.bot.send_voice(
                        admin_id,
                        file_id,
                        caption=notify_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    await context.bot.send_message(
                        admin_id,
                        notify_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
            except Exception as e:
                logger.warning(f"Не удалось уведомить админа {admin_id}: {e}")

    # Подтверждаем отправку
    await update.message.reply_text(
        "✅ Сообщение отправлено!\n\n"
        "Продолжайте писать или нажмите кнопку ниже:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Закрыть чат", callback_data="chat_close")]
        ])
    )

    return CHAT_STEP


async def cancel_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Закрытие чата"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    order_id = context.user_data.get('chat_order_id')

    # Очищаем данные чата
    context.user_data.pop('chat_order_id', None)
    context.user_data.pop('chat_is_admin', None)

    if is_admin(user_id):
        # Возвращаем в админку
        if order_id:
            text = f"💬 Чат по заказу #{order_id} закрыт\n\n/admin — вернуться в панель"
        else:
            text = "💬 Чат закрыт\n\n/admin — вернуться в панель"
    else:
        text = "💬 Чат закрыт\n\n/start — вернуться в меню"

    await query.edit_message_text(text)

    return ConversationHandler.END
