from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import ADMIN_IDS

def main_kb(user_id):
    """Главное меню."""
    kb = [
        [InlineKeyboardButton("📝 Заказать работу", callback_data="order_start")],
        [
            InlineKeyboardButton("👤 Профиль", callback_data="profile"),
            InlineKeyboardButton("💰 Прайс", callback_data="price_list")
        ],
        [
            InlineKeyboardButton("🎁 Бонус дня", callback_data="daily_bonus"),
            InlineKeyboardButton("🎲 Дуэль", callback_data="duel_start")
        ],
        [InlineKeyboardButton("✍️ Оставить отзыв", callback_data="write_review")],
    ]

    # Админская кнопка
    if user_id in ADMIN_IDS:
        kb.append([InlineKeyboardButton("🔐 CRM Админа", callback_data="adm_panel")])

    return InlineKeyboardMarkup(kb)

def profile_kb():
    """Меню профиля."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 Мои заказы", callback_data="my_history")],
        [InlineKeyboardButton("💳 История операций", callback_data="my_transactions")],
        [InlineKeyboardButton("🕸 Партнёрка", callback_data="partners")],
        [InlineKeyboardButton("🎟 Ввести промокод", callback_data="enter_promo")],
        [InlineKeyboardButton("📜 Кодекс Салуна", callback_data="code_honor")],
        [InlineKeyboardButton("🏠 Домой", callback_data="home")]
    ])

def back_kb(callback_data="home"):
    """Кнопка назад."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data=callback_data)]
    ])

def history_kb(orders):
    """Список заказов пользователя."""
    status_emoji = {"checking": "🟡", "work": "⚙️", "done": "✅", "cancel": "❌"}
    kb = []
    for o in orders[:10]:  # Максимум 10
        emoji = status_emoji.get(o['status'], "📦")
        short_topic = o['topic'][:20] + "..." if len(o['topic']) > 20 else o['topic']
        kb.append([InlineKeyboardButton(
            f"{emoji} #{o['id']} | {short_topic}",
            callback_data=f"my_order_{o['id']}"
        )])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="profile")])
    return InlineKeyboardMarkup(kb)

def order_details_kb(order_id, status):
    """Детали заказа."""
    kb = []
    if status == "done":
        kb.append([InlineKeyboardButton("✅ Подтвердить получение", callback_data=f"cli_approve_{order_id}")])
    if status in ("checking", "work"):
        kb.append([InlineKeyboardButton("💬 Чат с менеджером", callback_data=f"chat_order_{order_id}")])
    kb.append([InlineKeyboardButton("🗑 Удалить из истории", callback_data=f"cli_delete_{order_id}")])
    kb.append([InlineKeyboardButton("🔙 К заказам", callback_data="my_history")])
    return InlineKeyboardMarkup(kb)

# ===== КОДЕКС САЛУНА =====

def salon_code_welcome_kb():
    """Первый экран: приветствие с картинкой."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 Читать Кодекс Салуна", callback_data="code_read_full")],
    ])

def salon_code_short_kb():
    """Краткая версия кодекса."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Подробнее о традициях", callback_data="code_read_details")],
        [InlineKeyboardButton("✅ Всё понятно, принимаю!", callback_data="code_accept_start")]
    ])

def salon_code_full_kb():
    """Полная версия — кнопка принятия."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬆️ К краткой версии", callback_data="code_read_full")],
        [InlineKeyboardButton("✅ Принимаю традиции Салуна", callback_data="code_accept_start")]
    ])

def salon_code_checkboxes_kb(checks: dict):
    """
    Клавиатура с чекбоксами для принятия.
    checks = {"materials": False, "payment": False, "confidential": False}
    """
    def checkbox(checked):
        return "✅" if checked else "⬜️"

    kb = [
        [InlineKeyboardButton(
            f"{checkbox(checks.get('materials', False))} Работы — для изучения, использую сам",
            callback_data="code_check_materials"
        )],
        [InlineKeyboardButton(
            f"{checkbox(checks.get('payment', False))} Понимаю условия оплаты и правок",
            callback_data="code_check_payment"
        )],
        [InlineKeyboardButton(
            f"{checkbox(checks.get('confidential', False))} Храню тайну Салуна",
            callback_data="code_check_confidential"
        )],
    ]

    # Если все отмечены — показываем кнопку входа
    if all(checks.values()):
        kb.append([InlineKeyboardButton("🚪 Войти в Салун 🎁", callback_data="code_final_accept")])
    else:
        kb.append([InlineKeyboardButton("☝️ Отметь все пункты выше", callback_data="code_not_ready")])

    return InlineKeyboardMarkup(kb)

def salon_code_readonly_kb():
    """Кодекс для повторного просмотра (из профиля)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Полная версия", callback_data="code_view_full")],
        [InlineKeyboardButton("🔙 В профиль", callback_data="profile")]
    ])

# ===== УСЛУГИ И ПРАЙС =====

def services_kb():
    """Выбор типа услуги."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💋 Эссе / Статья", callback_data="srv_essay")],
        [InlineKeyboardButton("🌹 Курсовая работа", callback_data="srv_term")],
        [InlineKeyboardButton("💍 Диплом (ВКР)", callback_data="srv_diploma")],
        [InlineKeyboardButton("🎩 Отчёт по практике", callback_data="srv_practice")],
        [InlineKeyboardButton("🎲 Онлайн-экзамен", callback_data="srv_exam")],
        [InlineKeyboardButton("🏠 Домой", callback_data="home")]
    ])

def price_list_kb():
    """Меню прайс-листа."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💋 Эссе", callback_data="price_srv_essay")],
        [InlineKeyboardButton("🌹 Курсовая", callback_data="price_srv_term")],
        [InlineKeyboardButton("💍 Диплом", callback_data="price_srv_diploma")],
        [InlineKeyboardButton("🎩 Практика", callback_data="price_srv_practice")],
        [InlineKeyboardButton("🎲 Экзамен", callback_data="price_srv_exam")],
        [InlineKeyboardButton("🏠 Домой", callback_data="home")]
    ])

def deadline_kb():
    """Выбор срока выполнения."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡️ 1-2 дня", callback_data="time_urgent"),
            InlineKeyboardButton("📅 3-5 дней", callback_data="time_normal")
        ],
        [
            InlineKeyboardButton("🗓 Неделя+", callback_data="time_week"),
            InlineKeyboardButton("🐢 2+ недели", callback_data="time_relax")
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_topic")]
    ])

def upsell_kb(selected: dict):
    """Дополнительные услуги."""
    def check(key):
        return "✅ " if selected.get(key) else ""

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{check('speech')}🎤 Речь к защите (+1500₽)", callback_data="toggle_speech")],
        [InlineKeyboardButton(f"{check('pres')}📊 Презентация (+2000₽)", callback_data="toggle_pres")],
        [InlineKeyboardButton(f"{check('vip')}👑 VIP-сопровождение (+2500₽)", callback_data="toggle_vip")],
        [InlineKeyboardButton("✅ Готово, далее →", callback_data="upsell_done")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_deadline")]
    ])

def payment_kb(balance, price):
    """Выбор способа оплаты."""
    kb = [
        [InlineKeyboardButton("💵 Оплата переводом", callback_data="pay_cash")],
    ]

    if balance > 0:
        max_bonus = min(balance, int(price * 0.2))  # Максимум 20% бонусами
        if max_bonus > 0:
            kb.append([InlineKeyboardButton(
                f"🎁 Списать бонусы (до {max_bonus}₽)",
                callback_data="pay_bonus"
            )])

    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_upsell")])
    return InlineKeyboardMarkup(kb)

def confirm_order_kb():
    """Подтверждение заказа."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Подтвердить заказ", callback_data="submit_order")],
        [InlineKeyboardButton("🔙 Изменить", callback_data="order_start")]
    ])
