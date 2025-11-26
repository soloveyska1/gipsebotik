"""
👤 CLIENT HANDLERS - Клиентская часть бота
"""
import logging
import random
from html import escape
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from config import SERVICES, ADMIN_IDS, REVIEW_CHANNEL_ID
from database import core as db

logger = logging.getLogger(__name__)

# States
PROMO_STATE = 100
REVIEW_STATE = 101


def get_greeting(name):
    """Приветствие в зависимости от времени суток"""
    hour = datetime.now().hour
    if 6 <= hour < 12:
        return f"☀️ Доброе утро, <b>{name}</b>!"
    elif 12 <= hour < 18:
        return f"🌤 Добрый день, <b>{name}</b>!"
    elif 18 <= hour < 23:
        return f"🌆 Добрый вечер, <b>{name}</b>!"
    else:
        return f"🌙 Доброй ночи, <b>{name}</b>!"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню"""
    user = update.effective_user
    query = update.callback_query

    if query:
        await query.answer()

    # Регистрируем пользователя
    referrer_id = 0
    if context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])

    is_new = await db.add_user(
        user.id,
        user.username or '',
        user.full_name or 'Без имени',
        referrer_id=referrer_id
    )

    # Логируем действие
    await db.log_action(user.id, 'start', screen='main_menu')
    await db.track_funnel(user.id, 'start')

    # Получаем данные пользователя
    user_data = await db.get_user(user.id)
    orders_count = user_data.get('orders_count', 0) if user_data else 0

    # Формируем приветствие
    name = escape(user.first_name or 'друг')
    greeting = get_greeting(name)

    if is_new:
        text = f"{greeting}\n\n"
        text += "🎓 Добро пожаловать в <b>GipseBot</b>!\n\n"
        text += "Мы помогаем студентам с учебными работами:\n"
        text += "📝 Эссе и рефераты\n"
        text += "📚 Курсовые работы\n"
        text += "🎓 Дипломы и ВКР\n"
        text += "📊 Отчёты по практике\n\n"
        text += "Выберите действие 👇"
    else:
        text = f"{greeting}\n\n"
        if orders_count > 0:
            text += f"📦 У вас <b>{orders_count}</b> заказ(ов)\n\n"
        text += "Чем могу помочь? 👇"

    keyboard = [
        [InlineKeyboardButton("🔥 Сделать заказ", callback_data="order_start")],
        [
            InlineKeyboardButton("💰 Прайс", callback_data="price_list"),
            InlineKeyboardButton("👤 Профиль", callback_data="profile")
        ],
        [
            InlineKeyboardButton("📜 Правила", callback_data="code_honor"),
            InlineKeyboardButton("🤝 Партнёрка", callback_data="partners")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        try:
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        except:
            await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Профиль пользователя"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user = await db.get_user(user_id)

    await db.log_action(user_id, 'view_profile', screen='profile')

    if not user:
        await query.edit_message_text("❌ Профиль не найден. Нажмите /start")
        return

    orders = await db.get_user_orders(user_id)

    text = "👤 <b>ВАШ ПРОФИЛЬ</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    text += f"📛 <b>Имя:</b> {escape(user.get('full_name', 'Не указано'))}\n"
    text += f"🆔 <b>ID:</b> <code>{user_id}</code>\n\n"

    text += "📊 <b>Статистика:</b>\n"
    text += f"  📦 Заказов: {user.get('orders_count', 0)}\n"
    text += f"  ✅ Выполнено: {user.get('completed_orders', 0)}\n"
    text += f"  💰 Потрачено: {user.get('total_spent', 0)}₽\n\n"

    text += f"💎 <b>Баланс:</b> {user.get('balance', 0)}₽\n"
    text += f"🎁 <b>Бонусы:</b> {user.get('bonus_balance', 0)}₽\n\n"

    # VIP статус
    vip = user.get('vip_level', 0)
    if vip > 0:
        text += f"👑 <b>VIP статус:</b> Уровень {vip}\n"
        text += f"🏷 <b>Скидка:</b> {user.get('discount_percent', 0)}%\n\n"

    # Активные заказы
    active_orders = [o for o in orders if o['status'] not in ('done', 'cancelled')]
    if active_orders:
        text += f"📦 <b>Активные заказы ({len(active_orders)}):</b>\n"
        for o in active_orders[:3]:
            status_emoji = {'new': '🆕', 'checking': '🔍', 'in_progress': '⚙️', 'review': '📝'}.get(o['status'], '📦')
            text += f"  {status_emoji} #{o['id']} — {o.get('service_type', 'Заказ')[:20]}\n"

    keyboard = [
        [
            InlineKeyboardButton("📦 Мои заказы", callback_data="my_history"),
            InlineKeyboardButton("💳 Транзакции", callback_data="my_transactions")
        ],
        [
            InlineKeyboardButton("🎁 Ввести промокод", callback_data="enter_promo"),
            InlineKeyboardButton("⭐ Оставить отзыв", callback_data="write_review")
        ],
        [
            InlineKeyboardButton("🎰 Бонус дня", callback_data="daily_bonus"),
            InlineKeyboardButton("🤝 Партнёрка", callback_data="partners")
        ],
        [InlineKeyboardButton("🏠 Главная", callback_data="home")]
    ]

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))


async def my_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """История заказов"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    orders = await db.get_user_orders(user_id)

    await db.log_action(user_id, 'view_orders', screen='orders_history')

    text = "📦 <b>МОИ ЗАКАЗЫ</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    status_names = {
        'new': '🆕 Новый',
        'checking': '🔍 Проверка',
        'in_progress': '⚙️ В работе',
        'review': '📝 На проверке',
        'done': '✅ Выполнен',
        'cancelled': '❌ Отменён'
    }

    if orders:
        for o in orders[:10]:
            status = status_names.get(o['status'], o['status'])
            topic = escape((o.get('topic') or 'Без темы')[:30])
            text += f"<b>#{o['id']}</b> {status}\n"
            text += f"   📝 {topic}\n"
            text += f"   💰 {o.get('price', 0)}₽\n\n"
    else:
        text += "<i>У вас пока нет заказов</i>\n\n"
        text += "Нажмите «Сделать заказ» чтобы начать!"

    keyboard = []

    # Кнопки для перехода к деталям заказа
    for o in orders[:5]:
        keyboard.append([
            InlineKeyboardButton(f"📄 Заказ #{o['id']}",
                               callback_data=f"my_order_{o['id']}")
        ])

    keyboard.append([
        InlineKeyboardButton("🔥 Новый заказ", callback_data="order_start"),
        InlineKeyboardButton("👤 Профиль", callback_data="profile")
    ])
    keyboard.append([InlineKeyboardButton("🏠 Главная", callback_data="home")])

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))


async def my_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Детали конкретного заказа"""
    query = update.callback_query
    await query.answer()

    order_id = int(query.data.split("_")[-1])
    order = await db.get_order(order_id)

    if not order or order['user_id'] != update.effective_user.id:
        await query.edit_message_text("❌ Заказ не найден")
        return

    status_names = {
        'new': '🆕 Новый — ожидает проверки',
        'checking': '🔍 Проверяем детали',
        'in_progress': '⚙️ В работе у автора',
        'review': '📝 Готово, проверяем качество',
        'done': '✅ Выполнен',
        'cancelled': '❌ Отменён'
    }

    text = f"📦 <b>ЗАКАЗ #{order_id}</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    text += f"📌 <b>Статус:</b> {status_names.get(order['status'], order['status'])}\n\n"
    text += f"📝 <b>Тип:</b> {order.get('service_type', 'Не указан')}\n"
    text += f"📚 <b>Тема:</b> {escape(order.get('topic', 'Не указана')[:100])}\n"
    text += f"📅 <b>Дедлайн:</b> {order.get('deadline', 'Не указан')}\n"
    text += f"💰 <b>Стоимость:</b> {order.get('price', 0)}₽\n"
    text += f"💳 <b>Оплата:</b> {order.get('payment_status', 'ожидает оплаты')}\n"

    keyboard = [
        [InlineKeyboardButton("💬 Чат по заказу", callback_data=f"chat_order_{order_id}")]
    ]

    if order['status'] == 'done':
        keyboard.append([
            InlineKeyboardButton("⭐ Оставить отзыв", callback_data="write_review")
        ])

    keyboard.append([
        InlineKeyboardButton("📦 Все заказы", callback_data="my_history"),
        InlineKeyboardButton("🏠 Главная", callback_data="home")
    ])

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))


async def my_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """История транзакций"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    transactions = await db.get_transactions(user_id)

    text = "💳 <b>ТРАНЗАКЦИИ</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    if transactions:
        for t in transactions:
            amount = t.get('amount', 0)
            emoji = "➕" if amount > 0 else "➖"
            reason = t.get('reason', 'Операция')[:30]
            date = str(t.get('created_at', ''))[:10]
            text += f"{emoji} <b>{abs(amount)}₽</b> — {reason}\n"
            text += f"   📅 {date}\n\n"
    else:
        text += "<i>Транзакций пока нет</i>"

    keyboard = [
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🏠 Главная", callback_data="home")]
    ]

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))


async def show_price_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Прайс-лист"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    await db.log_action(user_id, 'view_price', screen='price_list')
    await db.track_funnel(user_id, 'view_services')

    text = "💰 <b>ПРАЙС-ЛИСТ</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    for key, service in SERVICES.items():
        emoji = service.get('emoji', '📝')
        name = service.get('name', key)
        base = service.get('base', 0)
        text += f"{emoji} <b>{name}</b>\n"
        text += f"   от <b>{base}₽</b>\n\n"

    text += "💡 <i>Точная цена зависит от сложности и срочности</i>\n\n"
    text += "⚡ <b>Срочный заказ:</b> +40% к цене\n"
    text += "🎁 <b>Постоянным клиентам:</b> скидки до 15%"

    keyboard = [
        [InlineKeyboardButton("🔥 Сделать заказ", callback_data="order_start")],
        [InlineKeyboardButton("🏠 Главная", callback_data="home")]
    ]

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))


async def show_price_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Карточка конкретной услуги"""
    query = update.callback_query
    await query.answer()

    service_key = query.data.replace("price_srv_", "")
    service = SERVICES.get(service_key)

    if not service:
        await query.edit_message_text("❌ Услуга не найдена")
        return

    text = f"{service.get('emoji', '📝')} <b>{service.get('name')}</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"{service.get('desc', '')}\n\n"
    text += f"💰 <b>Базовая цена:</b> от {service.get('base', 0)}₽\n\n"
    text += service.get('script', '')

    keyboard = [
        [InlineKeyboardButton("🔥 Заказать", callback_data=f"srv_{service_key}")],
        [InlineKeyboardButton("💰 Прайс", callback_data="price_list")],
        [InlineKeyboardButton("🏠 Главная", callback_data="home")]
    ]

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))


async def partners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Партнёрская программа"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    bot = await context.bot.get_me()

    ref_link = f"https://t.me/{bot.username}?start={user_id}"

    text = "🤝 <b>ПАРТНЁРСКАЯ ПРОГРАММА</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    text += "Приглашай друзей и получай <b>10%</b> от их первого заказа!\n\n"

    text += "📊 <b>Твоя статистика:</b>\n"
    text += f"  👥 Приглашено: <i>скоро</i>\n"
    text += f"  💰 Заработано: {user.get('referral_earnings', 0) if user else 0}₽\n\n"

    text += "🔗 <b>Твоя ссылка:</b>\n"
    text += f"<code>{ref_link}</code>\n\n"

    text += "<i>Нажми на ссылку чтобы скопировать</i>"

    keyboard = [
        [InlineKeyboardButton("📤 Поделиться", switch_inline_query=f"Закажи работу тут: {ref_link}")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🏠 Главная", callback_data="home")]
    ]

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))


async def show_code_of_honor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Правила сервиса"""
    query = update.callback_query
    await query.answer()

    text = "📜 <b>ПРАВИЛА СЕРВИСА</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    text += "✅ <b>Мы гарантируем:</b>\n"
    text += "• Уникальность работ (проверка на антиплагиат)\n"
    text += "• Соблюдение сроков\n"
    text += "• Бесплатные правки в течение 14 дней\n"
    text += "• Конфиденциальность\n\n"

    text += "❌ <b>Мы НЕ делаем:</b>\n"
    text += "• Работы за 1-2 дня (минимум 3 дня)\n"
    text += "• Медицинские/юридические заключения\n"
    text += "• Работы с нарушением закона\n\n"

    text += "💳 <b>Оплата:</b>\n"
    text += "• Предоплата 50% после согласования\n"
    text += "• Остаток — после сдачи работы\n\n"

    text += "📞 По всем вопросам: @admin"

    keyboard = [
        [InlineKeyboardButton("✅ Принимаю правила", callback_data="rules_accept")],
        [InlineKeyboardButton("🏠 Главная", callback_data="home")]
    ]

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))


async def accept_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принятие правил"""
    query = update.callback_query
    await query.answer("✅ Правила приняты!")
    await start(update, context)


# ==================== БОНУС ДНЯ ====================

async def play_daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ежедневный бонус — слоты"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    # Простая игра в слоты
    symbols = ['🍒', '🍋', '🍊', '🍇', '💎', '7️⃣']
    result = [random.choice(symbols) for _ in range(3)]

    text = "🎰 <b>БОНУС ДНЯ</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    text += f"[ {' | '.join(result)} ]\n\n"

    # Проверяем выигрыш
    if result[0] == result[1] == result[2]:
        if result[0] == '💎':
            bonus = 500
            text += "💎💎💎 <b>ДЖЕКПОТ!</b> +500₽ на баланс!"
        elif result[0] == '7️⃣':
            bonus = 300
            text += "7️⃣7️⃣7️⃣ <b>СУПЕР!</b> +300₽ на баланс!"
        else:
            bonus = 100
            text += f"{result[0]}{result[0]}{result[0]} <b>Победа!</b> +100₽ на баланс!"

        # Начисляем бонус
        user = await db.get_user(user_id)
        if user:
            new_balance = user.get('bonus_balance', 0) + bonus
            await db.update_user_field(user_id, 'bonus_balance', new_balance)
    elif result[0] == result[1] or result[1] == result[2]:
        text += "🎯 Почти! Попробуй ещё раз завтра!"
    else:
        text += "😔 Не повезло... Попробуй завтра!"

    text += "\n\n<i>Бонусы можно использовать при оплате заказа</i>"

    keyboard = [
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🏠 Главная", callback_data="home")]
    ]

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))


# ==================== ПРОМОКОД ====================

async def ask_promo_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос промокода"""
    query = update.callback_query
    await query.answer()

    text = "🎁 <b>ВВОД ПРОМОКОДА</b>\n\n"
    text += "Введите промокод:"

    await query.edit_message_text(text, parse_mode=ParseMode.HTML)

    return PROMO_STATE


async def submit_promo_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка промокода"""
    code = update.message.text.strip().upper()

    # TODO: Проверка промокода в БД
    # Пока просто заглушка

    if code == "WELCOME":
        await update.message.reply_text(
            "✅ <b>Промокод активирован!</b>\n\n"
            "Вам начислена скидка 10% на первый заказ!",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            "❌ Промокод не найден или уже использован\n\n"
            "/start — вернуться в меню",
            parse_mode=ParseMode.HTML
        )

    return ConversationHandler.END


# ==================== ОТЗЫВ ====================

async def ask_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос отзыва"""
    query = update.callback_query
    await query.answer()

    text = "⭐ <b>ОСТАВИТЬ ОТЗЫВ</b>\n\n"
    text += "Напишите ваш отзыв о нашем сервисе.\n"
    text += "Можете прикрепить фото работы!\n\n"
    text += "<i>Ваш отзыв поможет нам стать лучше</i>"

    await query.edit_message_text(text, parse_mode=ParseMode.HTML)

    return REVIEW_STATE


async def submit_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение отзыва"""
    user = update.effective_user
    user_id = user.id

    text = update.message.text or update.message.caption or "Отзыв без текста"

    # Сохраняем в БД
    await db.add_review(user_id, text)

    # Отправляем в канал отзывов
    if REVIEW_CHANNEL_ID:
        try:
            review_text = f"⭐ <b>Новый отзыв</b>\n\n"
            review_text += f"👤 {escape(user.full_name or 'Аноним')}\n"
            review_text += f"💬 {escape(text)}"

            if update.message.photo:
                await context.bot.send_photo(
                    REVIEW_CHANNEL_ID,
                    update.message.photo[-1].file_id,
                    caption=review_text,
                    parse_mode=ParseMode.HTML
                )
            else:
                await context.bot.send_message(
                    REVIEW_CHANNEL_ID,
                    review_text,
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            logger.error(f"Ошибка отправки отзыва в канал: {e}")

    await update.message.reply_text(
        "✅ <b>Спасибо за отзыв!</b>\n\n"
        "Ваше мнение очень важно для нас!\n\n"
        "/start — вернуться в меню",
        parse_mode=ParseMode.HTML
    )

    return ConversationHandler.END


async def cancel_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена отзыва"""
    query = update.callback_query
    await query.answer()
    await profile(update, context)
    return ConversationHandler.END


# ==================== ПАСХАЛКИ ====================

async def handle_thanks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Реакция на 'спасибо'"""
    text = update.message.text.lower() if update.message.text else ""

    thanks_words = ['спасибо', 'благодарю', 'спс', 'thanks', 'thx']

    if any(word in text for word in thanks_words):
        responses = [
            "Всегда пожалуйста! 😊",
            "Рад помочь! 🤝",
            "Обращайтесь! ✨",
            "Не за что! 💪"
        ]
        await update.message.reply_text(random.choice(responses))


# ==================== ЗАГЛУШКИ ====================

async def open_safe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сейф — заглушка"""
    query = update.callback_query
    await query.answer("🔒 Функция в разработке")


async def send_safe_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка файла из сейфа — заглушка"""
    query = update.callback_query
    await query.answer("🔒 Функция в разработке")


async def start_duel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Дуэль — заглушка"""
    query = update.callback_query
    await query.answer("⚔️ Функция в разработке")


async def resolve_duel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Результат дуэли — заглушка"""
    query = update.callback_query
    await query.answer("⚔️ Функция в разработке")


async def draw_deadline_oracle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Оракул дедлайнов — заглушка"""
    query = update.callback_query
    await query.answer("🔮 Функция в разработке")


async def cli_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Одобрение клиентом — заглушка"""
    query = update.callback_query
    await query.answer("✅ Принято")


async def cli_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление клиентом — заглушка"""
    query = update.callback_query
    await query.answer("🗑 Удалено")
