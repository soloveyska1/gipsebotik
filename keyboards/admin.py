"""
Клавиатуры для супер-админки.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# === ГЛАВНАЯ ПАНЕЛЬ ===

def admin_main_kb():
    """Главное меню админки."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👥 Клиенты", callback_data="adm_clients"),
            InlineKeyboardButton("📋 Заказы", callback_data="adm_orders")
        ],
        [
            InlineKeyboardButton("💰 Финансы", callback_data="adm_finance"),
            InlineKeyboardButton("📊 Аналитика", callback_data="adm_analytics")
        ],
        [
            InlineKeyboardButton("📢 Рассылка", callback_data="adm_broadcast"),
            InlineKeyboardButton("🎁 Промокоды", callback_data="adm_promos")
        ],
        [
            InlineKeyboardButton("⚙️ Настройки", callback_data="adm_settings"),
            InlineKeyboardButton("🔔 Уведомления", callback_data="adm_notifications")
        ],
        [InlineKeyboardButton("🔄 Обновить", callback_data="adm_refresh")],
        [InlineKeyboardButton("🚪 Выйти", callback_data="home")]
    ])


# === КЛИЕНТЫ ===

def clients_list_kb(page=1, total_pages=1, filter_type=None):
    """Список клиентов с пагинацией."""
    kb = []

    # Фильтры
    filters = [
        ("Все", "all"),
        ("С заказами", "with_orders"),
        ("Без заказов", "without_orders"),
        ("Забаненные", "banned")
    ]

    filter_row = []
    for name, ftype in filters:
        prefix = "✓ " if filter_type == ftype or (filter_type is None and ftype == "all") else ""
        filter_row.append(InlineKeyboardButton(f"{prefix}{name}", callback_data=f"adm_cli_filter_{ftype}"))

    kb.append(filter_row[:2])
    kb.append(filter_row[2:])

    # Поиск
    kb.append([InlineKeyboardButton("🔍 Поиск клиента", callback_data="adm_cli_search")])

    # Пагинация
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("◀️", callback_data=f"adm_cli_page_{page-1}"))
    nav_row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="adm_cli_noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"adm_cli_page_{page+1}"))

    if nav_row:
        kb.append(nav_row)

    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="adm_panel")])

    return InlineKeyboardMarkup(kb)


def client_card_kb(user_id, is_banned=False, is_watched=False):
    """Карточка клиента с действиями."""
    watch_text = "👁 Снять слежку" if is_watched else "👁 Мониторинг"
    ban_text = "✅ Разбанить" if is_banned else "🚫 Бан"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💬 Написать", callback_data=f"adm_chat_{user_id}"),
            InlineKeyboardButton("💰 Баланс +/-", callback_data=f"adm_balance_{user_id}")
        ],
        [
            InlineKeyboardButton(ban_text, callback_data=f"adm_ban_{user_id}"),
            InlineKeyboardButton("📝 Заметка", callback_data=f"adm_note_{user_id}")
        ],
        [
            InlineKeyboardButton(watch_text, callback_data=f"adm_watch_{user_id}"),
            InlineKeyboardButton("📋 Заказы", callback_data=f"adm_cli_orders_{user_id}")
        ],
        [InlineKeyboardButton("🔙 К списку", callback_data="adm_clients")]
    ])


# === ЗАКАЗЫ ===

def orders_list_kb(page=1, total_pages=1, status_filter=None):
    """Список заказов с фильтрами."""
    kb = []

    # Фильтры по статусу
    statuses = [
        ("Все", "all", "📋"),
        ("Проверка", "checking", "🟡"),
        ("Работа", "work", "⚙️"),
        ("Готово", "done", "✅"),
        ("Отмена", "cancel", "❌")
    ]

    filter_row = []
    for name, status, emoji in statuses[:3]:
        prefix = "✓" if status_filter == status or (status_filter is None and status == "all") else emoji
        filter_row.append(InlineKeyboardButton(f"{prefix}", callback_data=f"adm_ord_filter_{status}"))
    kb.append(filter_row)

    filter_row2 = []
    for name, status, emoji in statuses[3:]:
        prefix = "✓" if status_filter == status else emoji
        filter_row2.append(InlineKeyboardButton(f"{prefix}", callback_data=f"adm_ord_filter_{status}"))
    kb.append(filter_row2)

    # Пагинация
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("◀️", callback_data=f"adm_ord_page_{page-1}"))
    nav_row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="adm_ord_noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"adm_ord_page_{page+1}"))

    if nav_row:
        kb.append(nav_row)

    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="adm_panel")])

    return InlineKeyboardMarkup(kb)


def order_card_kb(order_id, status):
    """Карточка заказа с действиями."""
    kb = []

    # Смена статуса
    if status == "checking":
        kb.append([
            InlineKeyboardButton("⚙️ В работу", callback_data=f"adm_ord_status_{order_id}_work"),
            InlineKeyboardButton("❌ Отменить", callback_data=f"adm_ord_status_{order_id}_cancel")
        ])
    elif status == "work":
        kb.append([
            InlineKeyboardButton("✅ Готов", callback_data=f"adm_ord_status_{order_id}_done"),
            InlineKeyboardButton("❌ Отменить", callback_data=f"adm_ord_status_{order_id}_cancel")
        ])
    elif status == "done":
        kb.append([InlineKeyboardButton("🔄 Вернуть в работу", callback_data=f"adm_ord_status_{order_id}_work")])
    elif status == "cancel":
        kb.append([InlineKeyboardButton("🔄 Восстановить", callback_data=f"adm_ord_status_{order_id}_checking")])

    kb.append([
        InlineKeyboardButton("💬 Клиенту", callback_data=f"adm_ord_chat_{order_id}"),
        InlineKeyboardButton("💰 Цена", callback_data=f"adm_ord_price_{order_id}")
    ])
    kb.append([
        InlineKeyboardButton("📎 Отправить файл", callback_data=f"adm_ord_file_{order_id}"),
        InlineKeyboardButton("📝 Заметка", callback_data=f"adm_ord_note_{order_id}")
    ])
    kb.append([InlineKeyboardButton("🔙 К заказам", callback_data="adm_orders")])

    return InlineKeyboardMarkup(kb)


# === ФИНАНСЫ ===

def finance_kb():
    """Меню финансов."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 По услугам", callback_data="adm_fin_services")],
        [InlineKeyboardButton("📅 За период", callback_data="adm_fin_period")],
        [InlineKeyboardButton("🎁 Бонусы", callback_data="adm_fin_bonuses")],
        [InlineKeyboardButton("📤 Экспорт", callback_data="adm_fin_export")],
        [InlineKeyboardButton("🔙 Назад", callback_data="adm_panel")]
    ])


# === АНАЛИТИКА ===

def analytics_kb():
    """Меню аналитики."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Конверсия", callback_data="adm_an_conversion")],
        [InlineKeyboardButton("👥 Топ рефереров", callback_data="adm_an_referrals")],
        [InlineKeyboardButton("🎁 Промокоды", callback_data="adm_an_promos")],
        [InlineKeyboardButton("📊 Активность", callback_data="adm_an_activity")],
        [InlineKeyboardButton("🔙 Назад", callback_data="adm_panel")]
    ])


# === РАССЫЛКА ===

def broadcast_kb():
    """Меню рассылки."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Всем", callback_data="adm_bc_all")],
        [InlineKeyboardButton("🛒 С заказами", callback_data="adm_bc_with_orders")],
        [InlineKeyboardButton("🆕 Без заказов", callback_data="adm_bc_without_orders")],
        [InlineKeyboardButton("👑 VIP", callback_data="adm_bc_vip")],
        [InlineKeyboardButton("🔙 Назад", callback_data="adm_panel")]
    ])


def broadcast_confirm_kb(filter_type, count):
    """Подтверждение рассылки."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📤 Отправить ({count} чел.)", callback_data=f"adm_bc_send_{filter_type}")],
        [InlineKeyboardButton("👁 Предпросмотр", callback_data="adm_bc_preview")],
        [InlineKeyboardButton("❌ Отмена", callback_data="adm_broadcast")]
    ])


# === ПРОМОКОДЫ ===

def promos_kb():
    """Меню промокодов."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Создать", callback_data="adm_promo_create")],
        [InlineKeyboardButton("📊 Статистика", callback_data="adm_promo_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="adm_panel")]
    ])


def promo_card_kb(code, is_active):
    """Карточка промокода."""
    toggle_text = "🔴 Выключить" if is_active else "🟢 Включить"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_text, callback_data=f"adm_promo_toggle_{code}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="adm_promo_stats")]
    ])


# === НАСТРОЙКИ ===

def settings_kb():
    """Меню настроек."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Тексты", callback_data="adm_set_texts")],
        [InlineKeyboardButton("💰 Цены", callback_data="adm_set_prices")],
        [InlineKeyboardButton("🎮 Функции", callback_data="adm_set_features")],
        [InlineKeyboardButton("💾 Бэкап БД", callback_data="adm_set_backup")],
        [InlineKeyboardButton("🔙 Назад", callback_data="adm_panel")]
    ])


# === УВЕДОМЛЕНИЯ ===

def notifications_kb(settings=None):
    """Настройки уведомлений."""
    if settings is None:
        settings = {}

    def check(key):
        return "✅" if settings.get(key, True) else "❌"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{check('new_users')} Новые пользователи", callback_data="adm_notif_toggle_new_users")],
        [InlineKeyboardButton(f"{check('new_orders')} Новые заказы", callback_data="adm_notif_toggle_new_orders")],
        [InlineKeyboardButton(f"{check('messages')} Сообщения", callback_data="adm_notif_toggle_messages")],
        [InlineKeyboardButton(f"{check('order_status')} Статусы заказов", callback_data="adm_notif_toggle_order_status")],
        [InlineKeyboardButton(f"{check('promos')} Промокоды", callback_data="adm_notif_toggle_promos")],
        [InlineKeyboardButton(f"{check('reviews')} Отзывы", callback_data="adm_notif_toggle_reviews")],
        [InlineKeyboardButton(f"{check('security')} Безопасность", callback_data="adm_notif_toggle_security")],
        [InlineKeyboardButton("🔙 Назад", callback_data="adm_panel")]
    ])


# === ЧАТ С КЛИЕНТОМ ===

def admin_chat_kb(user_id):
    """Клавиатура чата с клиентом."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📎 Файл", callback_data=f"adm_chat_file_{user_id}"),
            InlineKeyboardButton("📷 Фото", callback_data=f"adm_chat_photo_{user_id}")
        ],
        [InlineKeyboardButton("🔙 К клиенту", callback_data=f"adm_client_{user_id}")]
    ])


# === БЫСТРЫЕ ДЕЙСТВИЯ ИЗ УВЕДОМЛЕНИЙ ===

def quick_order_kb(order_id):
    """Быстрые действия для нового заказа."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ В работу", callback_data=f"adm_ord_status_{order_id}_work"),
            InlineKeyboardButton("💬 Написать", callback_data=f"adm_ord_chat_{order_id}")
        ],
        [InlineKeyboardButton("🔍 Подробнее", callback_data=f"adm_order_{order_id}")]
    ])


def quick_user_kb(user_id):
    """Быстрые действия для нового пользователя."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💬 Написать", callback_data=f"adm_chat_{user_id}"),
            InlineKeyboardButton("👤 Профиль", callback_data=f"adm_client_{user_id}")
        ]
    ])


def quick_message_kb(user_id, order_id=None):
    """Быстрые действия для сообщения."""
    kb = [[InlineKeyboardButton("💬 Ответить", callback_data=f"adm_chat_{user_id}")]]
    if order_id:
        kb.append([InlineKeyboardButton("📋 К заказу", callback_data=f"adm_order_{order_id}")])
    return InlineKeyboardMarkup(kb)


# === ВСПОМОГАТЕЛЬНЫЕ ===

def back_kb(callback_data="adm_panel"):
    """Кнопка назад."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data=callback_data)]
    ])


def confirm_kb(action, item_id):
    """Подтверждение действия."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да", callback_data=f"adm_confirm_{action}_{item_id}"),
            InlineKeyboardButton("❌ Нет", callback_data="adm_panel")
        ]
    ])


def cancel_kb():
    """Кнопка отмены."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data="adm_panel")]
    ])
