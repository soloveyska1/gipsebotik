from telegram import Update, InputMediaPhoto
from telegram.ext import ContextTypes, ConversationHandler
from database import core as db
from keyboards import menu as kb
from config import REVIEW_CHANNEL_ID
import utils

# === КОНСТАНТЫ ===

WELCOME_PHOTO_ID = "AgACAgIAAxkBAAIRBGkf3jybt7UiWBtsS4itzUfhWvceAALIC2sb7NgAAUkgNJP7MzMPsAEAAwIAA3kAAzYE"

REVIEW_STATE = 1
PROMO_STATE = 2

# Бонус за вступление (в рублях/монетах)
WELCOME_BONUS_AMOUNT = 100
# Максимум бонусов можно потратить = 20% от заказа
MAX_BONUS_PERCENT = 0.20

# === ТЕКСТЫ ПОСВЯЩЕНИЯ В КОВБОИ ===

def get_time_greeting():
    """Приветствие в зависимости от времени суток (МСК)."""
    from datetime import datetime, timezone, timedelta
    msk = timezone(timedelta(hours=3))
    hour = datetime.now(msk).hour

    if 5 <= hour < 12:
        return "Ранняя пташка! Кофе уже варится ☕"
    elif 12 <= hour < 17:
        return "В самое пекло заглянул, уважаю 🌵"
    elif 17 <= hour < 22:
        return "Вечерний гость — лучший гость 🌅"
    else:
        return "Полуночник? Мы тоже не спим 🌙"

# Главный экран посвящения (с картинкой)
INITIATION_WELCOME = """
<b>ЭЙ, {name}!</b>

{time_greeting}

Заходи, тут рады гостям. Вижу — дедлайны достали, преподы звереют. Знакомо.

<b>Расслабься. Ты в «Экспресс-Курсаче».</b>
Здесь помогут с любой учебной работой — быстро, качественно, секретно.
"""

# Что получит гость (второй экран или продолжение)
INITIATION_BENEFITS = """
🎁 <b>ЧТО ПОЛУЧИШЬ:</b>

✓ <b>{bonus}₽ на счёт</b> — прямо сейчас, за вход
✓ <b>3 раунда правок бесплатно</b> — докрутим до идеала
✓ <b>Работаем быстро:</b> эссе от 1 дня, курсач от 5
✓ <b>Полная секретность</b> — никто не узнает

━━━━━━━━━━━━━━━━━━━━

💰 <b>КАК ЭТО РАБОТАЕТ:</b>

Половина вперёд → делаем работу → показываем → платишь остаток.

Всё прозрачно. Никаких сюрпризов.
Если что не так — разберёмся по-честному.

━━━━━━━━━━━━━━━━━━━━

🤫 <b>И ГЛАВНОЕ:</b>

Что в Салуне — остаётся в Салуне.
Мы не спрашиваем лишнего. Ты не рассказываешь о нас.
Так спокойнее всем.
"""

# Полная версия для тех, кто хочет подробнее
INITIATION_FULL = """
📖 <b>ПОДРОБНЕЕ О САЛУНЕ</b>

<b>Сроки:</b>
• Эссе, статьи: <b>1-3 дня</b>
• Курсовые: <b>5-7 дней</b>
• Дипломы: <b>14-21 день</b>
• Срочно? Сделаем быстрее, но дороже

<b>Оплата:</b>
• 50% аванс — и мы начинаем
• 50% после — когда покажем результат
• Передумал до старта? Вернём без вопросов

<b>Правки:</b>
• 3 пакета бесплатно в рамках ТЗ
• Дальше — договоримся по-человечески

<b>Бонусы:</b>
• Копятся с каждого заказа
• Тратить можно до 20% от суммы

<b>Твоя добыча:</b>
Работа — твоя полностью.
Даём качественный материал для изучения.
Как используешь — твоё дело.

━━━━━━━━━━━━━━━━━━━━

<i>🎯 Секрет для внимательных:
Шепни бармену <code>FIRSTSHOT</code> — он поймёт</i>
"""

# Финальный экран после принятия
INITIATION_SUCCESS = """
🎉 <b>ДОБРО ПОЖАЛОВАТЬ, {name}!</b>

Ты теперь свой в Салуне.

🎁 <b>+{bonus}₽</b> уже на счёте — потрать на первый заказ!

<i>Удачи на Диком Западе знаний, ковбой!</i>

━━━━━━━━━━━━━━━━━━━━

👇 <b>Чем помочь?</b>
"""

# Текст для просмотра из профиля (уже принявшим)
INITIATION_READONLY = """
📜 <b>ТРАДИЦИИ САЛУНА</b>

Ты уже свой, но освежим память:

🎁 <b>Твои привилегии:</b>
• 3 раунда правок бесплатно
• Бонусы с каждого заказа (до 20% скидки)
• Полная конфиденциальность

💰 <b>Как работаем:</b>
• 50/50 — половина до, половина после
• Показываем результат перед финальной оплатой
• Проблемы решаем честно

⏰ <b>Сроки:</b>
• Эссе: 1-3 дня • Курсовая: 5-7 дней • Диплом: от 14 дней

<i>Что в Салуне — остаётся в Салуне 🤫</i>
"""

# === ОБРАБОТЧИКИ ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик /start — проверяет, принял ли пользователь Кодекс."""
    user = update.effective_user
    try:
        await utils.send_typing(context, update.effective_chat.id)
    except:
        pass

    # Парсим реферальный ID
    args = context.args if hasattr(context, 'args') and context.args else []
    ref_id = int(args[0]) if args and args[0].isdigit() else 0

    # Добавляем пользователя (если новый)
    is_new = await db.add_user(user.id, user.username, user.full_name, ref_id)

    # Уведомляем реферера
    if is_new and ref_id:
        try:
            await context.bot.send_message(ref_id, f"🤠 <b>Гость в салуне:</b> {user.full_name}", parse_mode="HTML")
        except:
            pass

    # Проверяем, принял ли Кодекс
    rules_accepted = await db.check_rules_accepted(user.id)

    if not rules_accepted:
        # Показываем Кодекс Салуна
        return await show_salon_code_welcome(update, context)
    else:
        # Показываем главное меню
        return await show_main_menu(update, context)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать главное меню."""
    user = update.effective_user
    greeting = utils.get_greeting(user.first_name)

    caption = (
        f"{greeting}\n\n"
        "Вижу, ты устал с дороги. Эта академическая пустыня кого угодно сведет с ума. "
        "Дедлайны палят как солнце, а преподы злее гремучих змей.\n\n"
        "Паркуй лошадь и расслабься. Ты в <b>«Экспресс-Курсаче»</b>. "
        "Здесь джентльмены решают вопросы, пока ты пьешь свой виски и наслаждаешься жизнью.\n\n"
        "👇 <b>Что нальём для храбрости?</b>"
    )

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.message.delete()
        except:
            pass
        await context.bot.send_photo(
            chat_id=user.id,
            photo=WELCOME_PHOTO_ID,
            caption=caption,
            reply_markup=kb.main_kb(user.id),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_photo(
            photo=WELCOME_PHOTO_ID,
            caption=caption,
            reply_markup=kb.main_kb(user.id),
            parse_mode="HTML"
        )


# ===== ПОСВЯЩЕНИЕ В КОВБОИ: ФЛОУ =====

async def show_initiation_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 1: Приветствие + выгоды (главный экран посвящения)."""
    user = update.effective_user

    # Собираем текст с приветствием по времени суток
    welcome = INITIATION_WELCOME.format(
        name=user.first_name,
        time_greeting=get_time_greeting()
    )
    benefits = INITIATION_BENEFITS.format(bonus=WELCOME_BONUS_AMOUNT)
    full_text = welcome + benefits

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.message.delete()
        except:
            pass

    # Отправляем с картинкой
    await context.bot.send_photo(
        chat_id=user.id,
        photo=WELCOME_PHOTO_ID,
        caption=full_text,
        reply_markup=kb.initiation_welcome_kb(),
        parse_mode="HTML"
    )


# Алиас для обратной совместимости
show_salon_code_welcome = show_initiation_welcome


async def show_initiation_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подробная версия для тех, кто хочет узнать больше."""
    query = update.callback_query
    await query.answer()

    try:
        await query.message.delete()
    except:
        pass

    await context.bot.send_message(
        chat_id=query.from_user.id,
        text=INITIATION_FULL,
        reply_markup=kb.initiation_details_kb(),
        parse_mode="HTML"
    )


async def toggle_initiation_agree(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключение чекбокса согласия."""
    query = update.callback_query

    # Инициализируем, если нет
    if 'initiation_agreed' not in context.user_data:
        context.user_data['initiation_agreed'] = False

    # Переключаем
    context.user_data['initiation_agreed'] = not context.user_data['initiation_agreed']

    await query.answer()

    # Обновляем клавиатуру
    await query.message.edit_reply_markup(
        reply_markup=kb.initiation_welcome_kb(context.user_data['initiation_agreed'])
    )


async def accept_initiation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Финальное принятие — вход в Салун."""
    query = update.callback_query
    user = query.from_user

    # Записываем принятие в БД
    await db.accept_rules(user.id)

    # Начисляем приветственный бонус
    bonus_given = await db.give_welcome_bonus(user.id, WELCOME_BONUS_AMOUNT)

    await query.answer("🎉 Добро пожаловать!", show_alert=True)

    # Очищаем состояние
    context.user_data.pop('initiation_agreed', None)

    # Показываем сообщение об успехе
    success_text = INITIATION_SUCCESS.format(
        name=user.first_name,
        bonus=WELCOME_BONUS_AMOUNT if bonus_given else 0
    )

    try:
        await query.message.delete()
    except:
        pass

    await context.bot.send_photo(
        chat_id=user.id,
        photo=WELCOME_PHOTO_ID,
        caption=success_text,
        reply_markup=kb.main_kb(user.id),
        parse_mode="HTML"
    )


async def initiation_not_agreed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь не отметил чекбокс."""
    query = update.callback_query
    await query.answer("👆 Сначала подтверди — поставь галочку выше", show_alert=True)


async def show_traditions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать традиции из профиля (для тех, кто уже в Салуне)."""
    query = update.callback_query
    await query.answer()

    await query.message.edit_text(
        INITIATION_READONLY,
        reply_markup=kb.traditions_readonly_kb(),
        parse_mode="HTML"
    )


async def show_traditions_full(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полная версия традиций (просмотр из профиля)."""
    query = update.callback_query
    await query.answer()

    await query.message.edit_text(
        INITIATION_FULL,
        reply_markup=kb.traditions_readonly_kb(),
        parse_mode="HTML"
    )


# === АЛИАСЫ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ ===
# (чтобы старые callback_data продолжали работать)
show_salon_code_short = show_initiation_welcome
show_salon_code_full = show_initiation_details
show_salon_code_checkboxes = show_initiation_welcome
toggle_checkbox = toggle_initiation_agree
code_not_ready = initiation_not_agreed
accept_salon_code = accept_initiation
show_code_of_honor = show_traditions
show_code_full_readonly = show_traditions_full


# ===== ПРОФИЛЬ И ПРОЧЕЕ =====

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Профиль пользователя."""
    query = update.callback_query
    await query.answer()

    u = await db.get_user(query.from_user.id)
    if not u:
        return await start(update, context)

    # Определяем ранг
    rank = get_user_rank(u['total_spent'], u['orders_count'])

    txt = (
        f"👤 <b>ЛИЧНОЕ ДЕЛО</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"🆔 ID: <code>{u['user_id']}</code>\n"
        f"🎖 Ранг: {rank}\n"
        f"💰 Баланс: <b>{u['balance']} ₽</b>\n"
        f"💸 Инвестировано: {u['total_spent']} ₽\n"
        f"📦 Заказов: {u['orders_count']}\n"
        f"━━━━━━━━━━━━━━\n"
        f"<i>Бонусы можно тратить до 20% от заказа</i>"
    )
    await query.edit_message_text(txt, reply_markup=kb.profile_kb(), parse_mode="HTML")


def get_user_rank(total_spent, orders_count):
    """Определить ранг пользователя."""
    if total_spent >= 50000:
        return "🌟 Легенда Запада"
    elif total_spent >= 20000:
        return "⭐️ Шериф"
    elif total_spent >= 10000:
        return "🔫 Рейнджер"
    elif orders_count >= 3:
        return "🎯 Стрелок"
    elif orders_count >= 1:
        return "🤠 Ковбой"
    else:
        return "🆕 Новичок"


async def partners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Партнёрская программа."""
    query = update.callback_query
    await query.answer()
    bot = await context.bot.get_me()
    link = f"https://t.me/{bot.username}?start={query.from_user.id}"
    text = (
        "🕸 <b>ЗОЛОТАЯ ЖИЛА</b>\n\n"
        "Приведи друга в Салун — получи <b>15%</b> от его первого заказа на свой баланс.\n\n"
        "👇 <b>Твоя ссылка:</b>\n"
        f"<code>{link}</code>\n\n"
        "<i>Скинь её другу — и золото потечёт рекой.</i>"
    )
    await query.edit_message_text(text, reply_markup=kb.back_kb("profile"), parse_mode="HTML")


async def my_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """История заказов."""
    query = update.callback_query
    await query.answer()
    orders = await db.get_user_orders(query.from_user.id)
    if not orders:
        await query.edit_message_text(
            "📂 <b>Архив пуст.</b>\n\n<i>Закажи первую работу — и она появится здесь.</i>",
            reply_markup=kb.profile_kb(),
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            "📂 <b>ТВОИ ДЕЛА:</b>",
            reply_markup=kb.history_kb(orders),
            parse_mode="HTML"
        )


async def my_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Детали заказа."""
    query = update.callback_query
    await query.answer()
    oid = int(query.data.split("_")[-1])
    o = await db.get_order(oid)

    if not o:
        return await my_history(update, context)

    status_map = {
        "checking": "🟡 На проверке",
        "work": "⚙️ В работе",
        "done": "✅ Готов",
        "cancel": "❌ Отмена"
    }

    txt = (
        f"📦 <b>ЗАКАЗ #{o['id']}</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"📚 Тип: {o['service_type']}\n"
        f"💰 Цена: {o['price']} ₽\n"
        f"📊 Статус: {status_map.get(o['status'], o['status'])}\n"
        f"📝 Тема: {o['topic']}"
    )
    await query.edit_message_text(txt, reply_markup=kb.order_details_kb(oid, o['status']), parse_mode="HTML")


async def my_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """История транзакций."""
    query = update.callback_query
    await query.answer()
    trans = await db.get_transactions(query.from_user.id)
    if not trans:
        return await query.edit_message_text(
            "💳 <b>Транзакций пока нет.</b>",
            reply_markup=kb.back_kb("profile"),
            parse_mode="HTML"
        )

    txt = "💳 <b>ИСТОРИЯ ОПЕРАЦИЙ:</b>\n\n"
    for t in trans:
        sign = "+" if t['amount'] > 0 else ""
        txt += f"📅 {t['date'][:16]}\n💴 <b>{sign}{t['amount']} ₽</b>\n<i>{t['reason']}</i>\n\n"

    await query.edit_message_text(txt, reply_markup=kb.back_kb("profile"), parse_mode="HTML")


# ===== ОТЗЫВЫ =====

async def ask_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос отзыва."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✍️ <b>Напиши пару слов:</b>\n\n"
        "Мы прибьём твой отзыв на доску почёта (в канал) анонимно.\n"
        "Кидай текст или скрин.",
        reply_markup=kb.back_kb("home"),
        parse_mode="HTML"
    )
    return REVIEW_STATE


async def submit_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка отзыва."""
    user = update.effective_user
    text = update.message.caption if update.message.caption else update.message.text
    if not text:
        text = "Без текста"

    await db.add_review(user.id, text)

    channel_text = (
        "🌵 <b>ВЕСТОЧКА ИЗ САЛУНА</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"{text}\n"
        "━━━━━━━━━━━━━━\n"
        "<i>#отзыв #салун</i>"
    )

    try:
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            await context.bot.send_photo(
                chat_id=REVIEW_CHANNEL_ID,
                photo=file_id,
                caption=channel_text,
                parse_mode="HTML"
            )
        else:
            await context.bot.send_message(
                chat_id=REVIEW_CHANNEL_ID,
                text=channel_text,
                parse_mode="HTML"
            )

        thanks_text = "✅ " + utils.get_random_phrase("done") + "\n\n<i>Твой отзыв опубликован. Спасибо!</i>"
        await update.message.reply_text(thanks_text, reply_markup=kb.main_kb(user.id), parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка шерифа: {e}",
            reply_markup=kb.main_kb(user.id)
        )

    return ConversationHandler.END


async def cancel_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена отзыва."""
    return ConversationHandler.END


# ===== ПРОМОКОДЫ =====

async def ask_promo_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос промокода."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🎟 <b>Введи промокод:</b>\n\n"
        "<i>Если у тебя есть секретное слово — шепни его сюда.</i>",
        reply_markup=kb.back_kb("profile"),
        parse_mode="HTML"
    )
    return PROMO_STATE


async def submit_promo_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка и активация промокода."""
    user = update.effective_user
    code = update.message.text.strip().upper()

    # Проверяем промокод
    promo = await db.check_promo_code(code, user.id)

    if promo is None:
        await update.message.reply_text(
            "❌ <b>Такого промокода нет.</b>\n\n<i>Проверь правильность написания.</i>",
            reply_markup=kb.back_kb("profile"),
            parse_mode="HTML"
        )
        return ConversationHandler.END

    if promo.get("error") == "already_used":
        await update.message.reply_text(
            "⚠️ <b>Ты уже использовал этот промокод.</b>",
            reply_markup=kb.back_kb("profile"),
            parse_mode="HTML"
        )
        return ConversationHandler.END

    if promo.get("error") == "max_uses":
        await update.message.reply_text(
            "⚠️ <b>Промокод больше не действует.</b>",
            reply_markup=kb.back_kb("profile"),
            parse_mode="HTML"
        )
        return ConversationHandler.END

    # Активируем промокод
    await db.use_promo_code(code, user.id)

    # Начисляем бонус
    if promo['bonus_amount'] > 0:
        await db.add_balance(user.id, promo['bonus_amount'], f"Промокод {code}")

    response = f"✅ <b>Промокод активирован!</b>\n\n"
    if promo['bonus_amount'] > 0:
        response += f"💰 +{promo['bonus_amount']}₽ на баланс\n"
    if promo['discount_percent'] > 0:
        response += f"🏷 Скидка {promo['discount_percent']}% на следующий заказ\n"

    await update.message.reply_text(
        response,
        reply_markup=kb.profile_kb(),
        parse_mode="HTML"
    )
    return ConversationHandler.END


# ===== ПРОЧИЕ ОБРАБОТЧИКИ =====

async def cli_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Клиент подтвердил выполнение заказа."""
    query = update.callback_query
    oid = int(query.data.split("_")[-1])
    await db.update_order_status(oid, "done")
    await query.answer("✅ Заказ подтверждён!")
    await my_order(update, context)


async def cli_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить заказ из истории."""
    query = update.callback_query
    oid = int(query.data.split("_")[-1])
    await db.update_order_visibility(oid, False)
    await query.answer("🗑 Удалено из истории")
    await my_history(update, context)


async def handle_thanks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пасхалка на слово 'спасибо'."""
    text = update.message.text.lower()
    if "спасибо" in text or "thanks" in text:
        phrases = [
            "🤠 Всегда пожалуйста, партнёр!",
            "🎩 Рад помочь, ковбой!",
            "🥃 За это не грех и выпить!",
            "🌵 Обращайся, если что!"
        ]
        import random
        await update.message.reply_text(random.choice(phrases))


# Заглушки для функций, которые будут в других модулях
async def play_daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🎰 Скоро будет доступно!", show_alert=True)

async def open_safe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔐 Сейф пока закрыт", show_alert=True)

async def send_safe_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def start_duel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⚔️ Дуэли скоро!", show_alert=True)

async def resolve_duel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def draw_deadline_oracle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔮 Оракул медитирует...", show_alert=True)

async def show_price_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    from config import SERVICES

    text = "💰 <b>ПРАЙС-ЛИСТ САЛУНА</b>\n━━━━━━━━━━━━━━\n\n"
    for key, srv in SERVICES.items():
        text += f"{srv['emoji']} <b>{srv['name']}</b>\nот {srv['base']}₽\n\n"

    text += (
        "━━━━━━━━━━━━━━\n"
        "⚡️ <i>Срочность +40% к цене</i>\n"
        "🎤 <i>Речь к защите +1500₽</i>\n"
        "📊 <i>Презентация +2000₽</i>\n"
        "👑 <i>VIP-сопровождение +2500₽</i>"
    )

    await query.edit_message_text(text, reply_markup=kb.back_kb("home"), parse_mode="HTML")


async def show_price_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass


async def accept_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Алиас для accept_salon_code (совместимость)."""
    return await accept_salon_code(update, context)
