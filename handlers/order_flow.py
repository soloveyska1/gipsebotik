"""
📝 ORDER FLOW - Оформление заказа
"""
import logging
import json
from html import escape
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from config import SERVICES
from database import core as db

logger = logging.getLogger(__name__)

# States
TYPE, TOPIC, DEADLINE, UPSELL, PAY_CHOICE, PAY_CUSTOM, CONFIRM = range(7)

# Дедлайны
DEADLINES = {
    'urgent': {'name': '🔥 Срочно (3-5 дней)', 'multiplier': 1.4, 'days': 4},
    'normal': {'name': '📅 Обычный (7-14 дней)', 'multiplier': 1.0, 'days': 10},
    'relaxed': {'name': '🌴 Спокойный (15-30 дней)', 'multiplier': 0.9, 'days': 20}
}

# Допы
UPSELLS = {
    'antiplagiat': {'name': '📊 Отчёт антиплагиат', 'price': 300},
    'presentation': {'name': '📽 Презентация', 'price': 500},
    'speech': {'name': '🎤 Речь к защите', 'price': 400}
}


async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало оформления заказа"""
    query = update.callback_query
    if query:
        await query.answer()

    user_id = update.effective_user.id
    await db.log_action(user_id, 'start_order', screen='order_type')
    await db.track_funnel(user_id, 'select_service')

    # Сбрасываем данные заказа
    context.user_data['order'] = {}

    text = "🔥 <b>НОВЫЙ ЗАКАЗ</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    text += "Выберите тип работы:\n"

    keyboard = []
    for key, service in SERVICES.items():
        emoji = service.get('emoji', '📝')
        name = service.get('name', key)
        price = service.get('base', 0)
        keyboard.append([
            InlineKeyboardButton(
                f"{emoji} {name} — от {price}₽",
                callback_data=f"srv_{key}"
            )
        ])

    keyboard.append([InlineKeyboardButton("🏠 Отмена", callback_data="home")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

    return TYPE


async def get_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор типа работы"""
    query = update.callback_query
    await query.answer()

    service_key = query.data.replace("srv_", "")
    service = SERVICES.get(service_key)

    if not service:
        await query.edit_message_text("❌ Услуга не найдена")
        return ConversationHandler.END

    user_id = update.effective_user.id
    await db.log_action(user_id, 'select_type', action_data=service_key, screen='order_topic')
    await db.track_funnel(user_id, 'enter_topic')

    # Сохраняем выбор
    context.user_data['order']['type'] = service_key
    context.user_data['order']['type_name'] = service.get('name')
    context.user_data['order']['base_price'] = service.get('base', 0)

    text = f"{service.get('emoji', '📝')} <b>{service.get('name')}</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"{service.get('script', 'Опишите вашу работу:')}\n\n"
    text += "📎 Можете прикрепить <b>файлы</b> (методичка, примеры)\n"
    text += "🎤 Или отправить <b>голосовое</b> сообщение"

    keyboard = [
        [InlineKeyboardButton("❓ Помощь с темой", callback_data="topic_help")],
        [InlineKeyboardButton("◀️ Назад", callback_data="srv_back")]
    ]

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))

    return TOPIC


async def get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение темы/описания"""
    user_id = update.effective_user.id

    # Обработка callback
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        if query.data == "topic_help":
            await query.edit_message_text(
                "💡 <b>Как описать работу?</b>\n\n"
                "1. Укажите <b>тему</b> работы\n"
                "2. Опишите <b>требования</b> (объём, антиплагиат)\n"
                "3. Прикрепите <b>методичку</b> если есть\n\n"
                "Пример:\n"
                "<i>«Курсовая по экономике на тему 'Инфляция в России'. "
                "30 страниц, антиплагиат от 70%»</i>\n\n"
                "Напишите вашу тему:",
                parse_mode=ParseMode.HTML
            )
            return TOPIC

        if query.data == "srv_back":
            return await start_order(update, context)

    # Обработка текста/файлов
    topic = ""
    files = []

    if update.message:
        if update.message.text:
            topic = update.message.text
        elif update.message.caption:
            topic = update.message.caption

        if update.message.document:
            files.append(update.message.document.file_id)
        if update.message.photo:
            files.append(update.message.photo[-1].file_id)
        if update.message.voice:
            files.append(f"voice:{update.message.voice.file_id}")

    if not topic and not files:
        await update.message.reply_text(
            "❌ Пожалуйста, опишите вашу работу или прикрепите файл"
        )
        return TOPIC

    await db.log_action(user_id, 'enter_topic', message=topic[:100], screen='order_deadline')
    await db.track_funnel(user_id, 'select_deadline')

    # Сохраняем
    context.user_data['order']['topic'] = topic or "Тема в файле"
    context.user_data['order']['files'] = ','.join(files)

    # Сохраняем брошенную корзину
    await db.save_abandoned_cart(
        user_id,
        'topic_entered',
        json.dumps(context.user_data['order'], ensure_ascii=False)
    )

    text = "📅 <b>ВЫБЕРИТЕ СРОК</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"📝 <b>Тема:</b> {escape(topic[:100]) if topic else 'В файле'}\n\n"
    text += "Когда нужна работа?"

    keyboard = []
    for key, dl in DEADLINES.items():
        keyboard.append([
            InlineKeyboardButton(dl['name'], callback_data=f"time_{key}")
        ])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_topic")])

    await update.message.reply_text(text, parse_mode=ParseMode.HTML,
                                    reply_markup=InlineKeyboardMarkup(keyboard))

    return DEADLINE


async def get_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор дедлайна"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    if query.data == "back_to_topic":
        # Возврат к вводу темы
        service_key = context.user_data['order'].get('type', 'essay')
        service = SERVICES.get(service_key, {})

        text = f"{service.get('emoji', '📝')} <b>{service.get('name', 'Работа')}</b>\n\n"
        text += "Опишите вашу работу:"

        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
        return TOPIC

    deadline_key = query.data.replace("time_", "")
    deadline = DEADLINES.get(deadline_key)

    if not deadline:
        await query.edit_message_text("❌ Ошибка выбора срока")
        return ConversationHandler.END

    await db.log_action(user_id, 'select_deadline', action_data=deadline_key, screen='order_upsell')
    await db.track_funnel(user_id, 'select_upsell')

    # Сохраняем
    context.user_data['order']['deadline'] = deadline_key
    context.user_data['order']['deadline_name'] = deadline['name']
    context.user_data['order']['multiplier'] = deadline['multiplier']

    # Рассчитываем цену
    base = context.user_data['order'].get('base_price', 0)
    price = int(base * deadline['multiplier'])
    context.user_data['order']['price'] = price
    context.user_data['order']['upsells'] = []

    text = "🎁 <b>ДОПОЛНИТЕЛЬНЫЕ УСЛУГИ</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"💰 Текущая стоимость: <b>{price}₽</b>\n\n"
    text += "Выберите дополнительные опции:"

    keyboard = []
    for key, upsell in UPSELLS.items():
        keyboard.append([
            InlineKeyboardButton(
                f"☐ {upsell['name']} +{upsell['price']}₽",
                callback_data=f"toggle_{key}"
            )
        ])

    keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="upsell_done")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_deadline")])

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))

    return UPSELL


async def get_upsell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор допов"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    if query.data == "back_to_deadline":
        text = "📅 <b>ВЫБЕРИТЕ СРОК</b>\n\n"
        text += "Когда нужна работа?"

        keyboard = []
        for key, dl in DEADLINES.items():
            keyboard.append([InlineKeyboardButton(dl['name'], callback_data=f"time_{key}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_topic")])

        await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                      reply_markup=InlineKeyboardMarkup(keyboard))
        return DEADLINE

    if query.data == "upsell_done":
        await db.log_action(user_id, 'upsell_done', screen='order_confirm')
        await db.track_funnel(user_id, 'confirm')
        return await show_confirmation(update, context)

    # Переключение допа
    upsell_key = query.data.replace("toggle_", "")
    upsells = context.user_data['order'].get('upsells', [])

    if upsell_key in upsells:
        upsells.remove(upsell_key)
    else:
        upsells.append(upsell_key)

    context.user_data['order']['upsells'] = upsells

    # Пересчитываем цену
    base = context.user_data['order'].get('base_price', 0)
    multiplier = context.user_data['order'].get('multiplier', 1.0)
    price = int(base * multiplier)

    for key in upsells:
        price += UPSELLS.get(key, {}).get('price', 0)

    context.user_data['order']['price'] = price

    # Обновляем кнопки
    text = "🎁 <b>ДОПОЛНИТЕЛЬНЫЕ УСЛУГИ</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"💰 Текущая стоимость: <b>{price}₽</b>\n\n"
    text += "Выберите дополнительные опции:"

    keyboard = []
    for key, upsell in UPSELLS.items():
        checked = "☑" if key in upsells else "☐"
        keyboard.append([
            InlineKeyboardButton(
                f"{checked} {upsell['name']} +{upsell['price']}₽",
                callback_data=f"toggle_{key}"
            )
        ])

    keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="upsell_done")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_deadline")])

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))

    return UPSELL


async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение заказа"""
    query = update.callback_query
    order = context.user_data.get('order', {})

    text = "📋 <b>ПОДТВЕРЖДЕНИЕ ЗАКАЗА</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    text += f"📝 <b>Тип:</b> {order.get('type_name', 'Не указан')}\n"
    text += f"📚 <b>Тема:</b> {escape(order.get('topic', 'Не указана')[:80])}\n"
    text += f"📅 <b>Срок:</b> {order.get('deadline_name', 'Не указан')}\n\n"

    # Допы
    upsells = order.get('upsells', [])
    if upsells:
        text += "🎁 <b>Дополнительно:</b>\n"
        for key in upsells:
            upsell = UPSELLS.get(key, {})
            text += f"  • {upsell.get('name', key)}\n"
        text += "\n"

    text += f"💰 <b>ИТОГО: {order.get('price', 0)}₽</b>\n\n"
    text += "✅ Подтвердите заказ или вернитесь к редактированию"

    keyboard = [
        [InlineKeyboardButton("🚀 ПОДТВЕРДИТЬ ЗАКАЗ", callback_data="submit_order")],
        [InlineKeyboardButton("◀️ Редактировать", callback_data="order_start")]
    ]

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))

    return CONFIRM


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Финальное подтверждение и создание заказа"""
    query = update.callback_query
    await query.answer()

    if query.data == "order_start":
        return await start_order(update, context)

    user_id = update.effective_user.id
    order = context.user_data.get('order', {})

    await db.log_action(user_id, 'submit_order', screen='order_created')
    await db.track_funnel(user_id, 'paid')  # или другой этап

    # Создаём заказ в БД
    order_data = {
        'user_id': user_id,
        'service_type': order.get('type', 'essay'),
        'service_name': order.get('type_name', 'Работа'),
        'topic': order.get('topic', 'Без темы'),
        'urgency': order.get('deadline', 'normal'),
        'deadline': order.get('deadline_name', 'Стандартный'),
        'base_price': order.get('base_price', 0),
        'final_price': order.get('price', 0),
        'upsells': order.get('upsells', []),
        'files': order.get('files', '').split(',') if order.get('files') else []
    }

    order_id = await db.create_order(order_data)

    # Очищаем данные заказа
    context.user_data['order'] = {}

    text = "✅ <b>ЗАКАЗ ОФОРМЛЕН!</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"🆔 <b>Номер заказа:</b> #{order_id}\n"
    text += f"💰 <b>К оплате:</b> {order_data['price']}₽\n\n"

    text += "📞 <b>Что дальше?</b>\n"
    text += "1. Менеджер свяжется с вами для уточнения деталей\n"
    text += "2. После согласования — предоплата 50%\n"
    text += "3. Работа будет готова в срок!\n\n"

    text += "💬 Используйте чат заказа для общения с менеджером"

    keyboard = [
        [InlineKeyboardButton("💬 Чат по заказу", callback_data=f"chat_order_{order_id}")],
        [InlineKeyboardButton("📦 Мои заказы", callback_data="my_history")],
        [InlineKeyboardButton("🏠 Главная", callback_data="home")]
    ]

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))

    return ConversationHandler.END


async def handle_payment_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора оплаты — заглушка"""
    query = update.callback_query
    await query.answer("💳 Функция оплаты в разработке")
    return CONFIRM


async def custom_points_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод своей суммы — заглушка"""
    await update.message.reply_text("💳 Функция в разработке")
    return ConversationHandler.END
