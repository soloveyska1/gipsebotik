"""
👑 ADMIN PANEL - ПОЛНЫЙ КОНТРОЛЬ
Всё перед глазами, каждое движение
"""
import logging
from datetime import datetime
from html import escape
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)
from telegram.constants import ParseMode

from config import ADMIN_IDS, LOG_CHANNEL_ID
from database import core as db

logger = logging.getLogger(__name__)

# States
BROADCAST_MSG, SEARCH_USER, ADD_NOTE, BAN_REASON = range(4)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def admin_only(func):
    """Декоратор для проверки админа"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not is_admin(user_id):
            return
        return await func(update, context)
    return wrapper


# ==================== ГЛАВНАЯ ПАНЕЛЬ ====================

@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главная панель админки"""
    query = update.callback_query
    if query:
        await query.answer()

    stats = await db.get_detailed_stats()
    online = await db.get_online_users()
    alerts = await db.get_unread_alerts(5)

    # Формируем сообщение
    text = "👑 <b>ADMIN PANEL</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    # Статистика
    text += "📊 <b>СТАТИСТИКА</b>\n"
    text += f"👥 Всего: <b>{stats['total_users']}</b> | "
    text += f"Сегодня: <b>+{stats['new_today']}</b>\n"
    text += f"🟢 Активных (7д): <b>{stats['active_week']}</b>\n\n"

    text += f"📦 Заказов: <b>{stats['total_orders']}</b>\n"
    text += f"🆕 Новых: <b>{stats['new_orders']}</b> | "
    text += f"В работе: <b>{stats['in_progress']}</b>\n\n"

    text += f"💰 Выручка: <b>{stats['total_revenue']:,}₽</b>\n"
    text += f"📈 Сегодня: <b>{stats['today_revenue']:,}₽</b>\n"
    text += f"⏳ Ожидает: <b>{stats['pending_revenue']:,}₽</b>\n\n"

    # Онлайн пользователи
    text += f"🟢 <b>ОНЛАЙН ({len(online)})</b>\n"
    if online:
        for u in online[:5]:
            name = escape(u.get('full_name', 'Без имени')[:15])
            action = u.get('last_action', '')[:20] if u.get('last_action') else 'в боте'
            text += f"  • {name} — <i>{action}</i>\n"
        if len(online) > 5:
            text += f"  <i>...и ещё {len(online) - 5}</i>\n"
    else:
        text += "  <i>Никого нет</i>\n"
    text += "\n"

    # Алерты
    alert_count = stats.get('unread_alerts', 0)
    if alert_count > 0:
        text += f"🔔 <b>АЛЕРТЫ ({alert_count})</b>\n"
        for a in alerts[:3]:
            text += f"  • {a['message'][:40]}\n"
        text += "\n"

    # Брошенные корзины
    if stats.get('abandoned_carts', 0) > 0:
        text += f"🛒 <b>Брошенных корзин:</b> {stats['abandoned_carts']}\n\n"

    keyboard = [
        [
            InlineKeyboardButton(f"📦 Заказы ({stats['new_orders']})", callback_data="adm_orders"),
            InlineKeyboardButton(f"👥 Юзеры", callback_data="adm_users")
        ],
        [
            InlineKeyboardButton(f"🔔 Алерты ({alert_count})", callback_data="adm_alerts"),
            InlineKeyboardButton("📊 Аналитика", callback_data="adm_analytics")
        ],
        [
            InlineKeyboardButton("🔥 Горячие лиды", callback_data="adm_hot_leads"),
            InlineKeyboardButton("🛒 Брошенные", callback_data="adm_abandoned")
        ],
        [
            InlineKeyboardButton("📣 Рассылка", callback_data="adm_broadcast"),
            InlineKeyboardButton("🔍 Поиск", callback_data="adm_search")
        ],
        [
            InlineKeyboardButton("📜 Лог действий", callback_data="adm_live_log"),
            InlineKeyboardButton("⚙️ Настройки", callback_data="adm_settings")
        ],
        [InlineKeyboardButton("🔄 Обновить", callback_data="adm_refresh")]
    ]

    if query:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                      reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML,
                                        reply_markup=InlineKeyboardMarkup(keyboard))


@admin_only
async def refresh_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обновить панель"""
    await admin_panel(update, context)


# ==================== ЗАКАЗЫ ====================

@admin_only
async def orders_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список заказов"""
    query = update.callback_query
    await query.answer()

    # Получаем фильтр из callback_data
    data = query.data
    status_filter = None
    if data.startswith("adm_orders_"):
        status_filter = data.replace("adm_orders_", "")

    orders = await db.get_all_orders(status=status_filter, limit=20)

    text = "📦 <b>ЗАКАЗЫ</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    status_emoji = {
        'new': '🆕',
        'checking': '🔍',
        'in_progress': '⚙️',
        'review': '📝',
        'done': '✅',
        'cancelled': '❌'
    }

    if orders:
        for o in orders:
            emoji = status_emoji.get(o['status'], '📦')
            topic = escape((o.get('topic') or '')[:25])
            name = escape((o.get('full_name') or 'Без имени')[:15])
            unread = await db.get_unread_messages_count(o['id'], is_admin=True)
            unread_badge = f" 💬{unread}" if unread else ""

            text += f"{emoji} <b>#{o['id']}</b> {topic}\n"
            text += f"   👤 {name} | 💰 {o.get('final_price', 0)}₽{unread_badge}\n\n"
    else:
        text += "<i>Нет заказов</i>\n"

    # Фильтры
    keyboard = [
        [
            InlineKeyboardButton("🆕 Новые", callback_data="adm_orders_new"),
            InlineKeyboardButton("⚙️ В работе", callback_data="adm_orders_in_progress"),
            InlineKeyboardButton("✅ Готовые", callback_data="adm_orders_done")
        ],
        [
            InlineKeyboardButton("📋 Все активные", callback_data="adm_orders")
        ]
    ]

    # Кнопки для каждого заказа
    for o in orders[:8]:
        keyboard.append([
            InlineKeyboardButton(f"#{o['id']} — {(o.get('topic') or '')[:20]}",
                               callback_data=f"adm_order_{o['id']}")
        ])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="adm_main")])

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))


@admin_only
async def order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Детали заказа"""
    query = update.callback_query
    await query.answer()

    order_id = int(query.data.split("_")[-1])
    order = await db.get_order(order_id)

    if not order:
        await query.edit_message_text("❌ Заказ не найден")
        return

    user = await db.get_user(order['user_id'])
    chat_history = await db.get_chat_history(order_id)

    status_names = {
        'new': '🆕 Новый',
        'checking': '🔍 Проверка',
        'in_progress': '⚙️ В работе',
        'review': '📝 На проверке',
        'done': '✅ Выполнен',
        'cancelled': '❌ Отменён'
    }

    text = f"📦 <b>ЗАКАЗ #{order_id}</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    text += f"📌 <b>Статус:</b> {status_names.get(order['status'], order['status'])}\n"
    text += f"📝 <b>Тип:</b> {order.get('service_name', 'Не указан')}\n"
    text += f"📚 <b>Тема:</b> {escape(order.get('topic', 'Не указана')[:100])}\n"
    text += f"📅 <b>Дедлайн:</b> {order.get('deadline', 'Не указан')}\n"
    text += f"💰 <b>Цена:</b> {order.get('final_price', 0)}₽\n"
    text += f"💳 <b>Оплата:</b> {order.get('payment_status', 'pending')}\n\n"

    # Информация о клиенте
    if user:
        text += "👤 <b>КЛИЕНТ</b>\n"
        text += f"  Имя: {escape(user.get('full_name', 'Не указано'))}\n"
        username = user.get('username')
        if username:
            text += f"  Username: @{username}\n"
        text += f"  ID: <code>{user['user_id']}</code>\n"
        text += f"  Заказов: {user.get('orders_count', 0)}\n"
        text += f"  Потрачено: {user.get('total_spent', 0)}₽\n"
        if user.get('tags'):
            text += f"  Теги: {user['tags']}\n"
        text += "\n"

    # Последние сообщения
    if chat_history:
        text += f"💬 <b>ЧАТ ({len(chat_history)} сообщ.)</b>\n"
        for msg in chat_history[-3:]:
            sender = "👤" if not msg['is_admin'] else "👑"
            content = escape((msg.get('content') or '')[:50])
            text += f"  {sender} {content}\n"
        text += "\n"

    # Заметки
    if order.get('internal_notes'):
        text += f"📝 <b>Заметки:</b>\n{escape(order['internal_notes'][:200])}\n\n"

    keyboard = [
        [
            InlineKeyboardButton("💬 Чат", callback_data=f"adm_chat_{order_id}"),
            InlineKeyboardButton("👤 Профиль", callback_data=f"adm_user_{order['user_id']}")
        ],
        [
            InlineKeyboardButton("✏️ Статус", callback_data=f"adm_status_{order_id}"),
            InlineKeyboardButton("💰 Оплата", callback_data=f"adm_payment_{order_id}")
        ],
        [
            InlineKeyboardButton("📝 Заметка", callback_data=f"adm_note_order_{order_id}"),
            InlineKeyboardButton("⚡ Приоритет", callback_data=f"adm_priority_{order_id}")
        ],
        [
            InlineKeyboardButton("✉️ Написать клиенту", callback_data=f"adm_dm_{order['user_id']}")
        ],
        [InlineKeyboardButton("◀️ К заказам", callback_data="adm_orders")]
    ]

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))


@admin_only
async def change_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Смена статуса заказа"""
    query = update.callback_query
    await query.answer()

    order_id = int(query.data.split("_")[-1])

    keyboard = [
        [InlineKeyboardButton("🆕 Новый", callback_data=f"adm_setstatus_{order_id}_new")],
        [InlineKeyboardButton("🔍 Проверка", callback_data=f"adm_setstatus_{order_id}_checking")],
        [InlineKeyboardButton("⚙️ В работе", callback_data=f"adm_setstatus_{order_id}_in_progress")],
        [InlineKeyboardButton("📝 На проверке", callback_data=f"adm_setstatus_{order_id}_review")],
        [InlineKeyboardButton("✅ Выполнен", callback_data=f"adm_setstatus_{order_id}_done")],
        [InlineKeyboardButton("❌ Отменён", callback_data=f"adm_setstatus_{order_id}_cancelled")],
        [InlineKeyboardButton("◀️ Назад", callback_data=f"adm_order_{order_id}")]
    ]

    await query.edit_message_text(
        f"📦 <b>Заказ #{order_id}</b>\n\nВыберите новый статус:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


@admin_only
async def set_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить статус"""
    query = update.callback_query
    await query.answer("✅ Статус обновлён")

    parts = query.data.split("_")
    order_id = int(parts[2])
    new_status = parts[3]

    await db.update_order_status(order_id, new_status)

    # Переход к деталям заказа
    context.user_data['_goto_order'] = order_id
    await order_detail(update, context)


# ==================== ПОЛЬЗОВАТЕЛИ ====================

@admin_only
async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список пользователей"""
    query = update.callback_query
    await query.answer()

    # Получаем фильтр
    data = query.data
    filter_type = None
    if "_" in data and data != "adm_users":
        filter_type = data.split("_")[-1]

    users = await db.get_all_users(limit=15, filter_type=filter_type)

    text = "👥 <b>ПОЛЬЗОВАТЕЛИ</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    for u in users:
        name = escape(u.get('full_name', 'Без имени')[:20])
        orders = u.get('orders_count', 0)
        spent = u.get('total_spent', 0)

        # Индикаторы
        badges = ""
        if u.get('is_banned'):
            badges += "🚫"
        if u.get('vip_level', 0) > 0:
            badges += "👑"
        if orders == 0:
            badges += "🆕"
        elif spent > 20000:
            badges += "🐳"

        text += f"{badges} <b>{name}</b>\n"
        text += f"   📦 {orders} заказов | 💰 {spent}₽\n\n"

    keyboard = [
        [
            InlineKeyboardButton("📋 Все", callback_data="adm_users"),
            InlineKeyboardButton("🟢 Активные", callback_data="adm_users_active")
        ],
        [
            InlineKeyboardButton("📦 С заказами", callback_data="adm_users_with_orders"),
            InlineKeyboardButton("🆕 Без заказов", callback_data="adm_users_no_orders")
        ],
        [
            InlineKeyboardButton("👑 VIP", callback_data="adm_users_vip"),
            InlineKeyboardButton("🚫 Забанены", callback_data="adm_users_banned")
        ],
        [
            InlineKeyboardButton("🔍 Поиск", callback_data="adm_search")
        ]
    ]

    # Кнопки к профилям
    for u in users[:5]:
        name = (u.get('full_name') or 'Без имени')[:20]
        keyboard.append([
            InlineKeyboardButton(f"👤 {name}",
                               callback_data=f"adm_user_{u['user_id']}")
        ])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="adm_main")])

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))


@admin_only
async def user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Профиль пользователя"""
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split("_")[-1])
    user = await db.get_user(user_id)

    if not user:
        await query.edit_message_text("❌ Пользователь не найден")
        return

    orders = await db.get_user_orders(user_id)
    actions = await db.get_user_actions(user_id, limit=10)

    text = "👤 <b>ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    # Основная инфа
    text += f"📛 <b>Имя:</b> {escape(user.get('full_name', 'Не указано'))}\n"
    if user.get('username'):
        text += f"📱 <b>Username:</b> @{user['username']}\n"
    text += f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
    text += f"📅 <b>Регистрация:</b> {str(user.get('created_at', 'Не известно'))[:10]}\n"
    text += f"🕐 <b>Последний визит:</b> {str(user.get('last_seen', ''))[:16]}\n\n"

    # Статистика
    text += "📊 <b>СТАТИСТИКА</b>\n"
    text += f"  📦 Заказов: {user.get('orders_count', 0)}\n"
    text += f"  ✅ Выполнено: {user.get('completed_orders', 0)}\n"
    text += f"  💰 Потрачено: {user.get('total_spent', 0)}₽\n"
    text += f"  🪙 Золото: {user.get('gold', 0)}\n"
    text += f"  🏆 Ранг: {user.get('rank', 'newcomer')}\n\n"

    # Теги и статус
    if user.get('is_banned'):
        text += f"🚫 <b>ЗАБАНЕН:</b> {user.get('ban_reason', 'Без причины')}\n\n"
    if user.get('tags'):
        text += f"🏷 <b>Теги:</b> {user['tags']}\n\n"

    # Заметки
    if user.get('notes'):
        text += f"📝 <b>Заметки:</b>\n<i>{escape(user['notes'][:200])}</i>\n\n"

    # Последние действия
    if actions:
        text += "🔍 <b>ПОСЛЕДНИЕ ДЕЙСТВИЯ</b>\n"
        for a in actions[:5]:
            time = str(a.get('created_at', ''))[-8:-3]
            action_text = a.get('action', a.get('data', ''))[:30]
            text += f"  {time} — {escape(action_text)}\n"
        text += "\n"

    # Заказы
    if orders:
        text += f"📦 <b>ЗАКАЗЫ ({len(orders)})</b>\n"
        for o in orders[:3]:
            status_emoji = {'new': '🆕', 'in_progress': '⚙️', 'done': '✅', 'completed': '✅'}.get(o['status'], '📦')
            text += f"  {status_emoji} #{o['id']} — {o.get('final_price', 0)}₽\n"

    keyboard = [
        [
            InlineKeyboardButton("✉️ Написать", callback_data=f"adm_dm_{user_id}"),
            InlineKeyboardButton("💬 История чатов", callback_data=f"adm_user_chats_{user_id}")
        ],
        [
            InlineKeyboardButton("📝 Добавить заметку", callback_data=f"adm_addnote_{user_id}"),
            InlineKeyboardButton("🏷 Теги", callback_data=f"adm_tags_{user_id}")
        ],
        [
            InlineKeyboardButton("👑 VIP статус", callback_data=f"adm_vip_{user_id}"),
            InlineKeyboardButton("💰 Баланс", callback_data=f"adm_balance_{user_id}")
        ],
        [
            InlineKeyboardButton(
                "🔓 Разбанить" if user.get('is_banned') else "🚫 Забанить",
                callback_data=f"adm_toggleban_{user_id}"
            )
        ],
        [
            InlineKeyboardButton("📜 Все действия", callback_data=f"adm_actions_{user_id}")
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="adm_users")]
    ]

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))


@admin_only
async def user_actions_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полный лог действий пользователя"""
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split("_")[-1])
    user = await db.get_user(user_id)
    actions = await db.get_user_actions(user_id, limit=30)

    text = f"📜 <b>ЛОГ ДЕЙСТВИЙ</b>\n"
    text += f"👤 {escape(user.get('full_name', 'Без имени') if user else 'Неизвестно')}\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    if actions:
        for a in actions:
            time = str(a.get('created_at', ''))[-8:-3]
            atype = a.get('action', 'action')
            msg = escape((a.get('data') or '')[:40])
            text += f"<code>{time}</code> [{atype}] {msg}\n"
    else:
        text += "<i>Нет данных</i>"

    keyboard = [[InlineKeyboardButton("◀️ К профилю", callback_data=f"adm_user_{user_id}")]]

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))


@admin_only
async def toggle_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Забанить/разбанить пользователя"""
    query = update.callback_query

    user_id = int(query.data.split("_")[-1])
    user = await db.get_user(user_id)

    if user and user.get('is_banned'):
        await db.unban_user(user_id)
        await query.answer("✅ Пользователь разбанен")
    else:
        await db.ban_user(user_id, "Заблокирован админом")
        await query.answer("🚫 Пользователь забанен")

    # Обновляем профиль
    await user_profile(update, context)


# ==================== АЛЕРТЫ ====================

@admin_only
async def alerts_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список алертов"""
    query = update.callback_query
    await query.answer()

    alerts = await db.get_unread_alerts(limit=20)

    text = "🔔 <b>АЛЕРТЫ</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    if alerts:
        for a in alerts:
            time = str(a.get('created_at', ''))[-8:-3]
            priority = "🔴" if a.get('priority', 0) >= 2 else "🟡" if a.get('priority') == 1 else "⚪"
            text += f"{priority} <code>{time}</code>\n"
            text += f"   {a['message']}\n"
            if a.get('username'):
                text += f"   👤 @{a['username']}\n"
            text += "\n"
    else:
        text += "<i>Нет новых алертов</i> ✨"

    keyboard = [
        [InlineKeyboardButton("✅ Прочитать все", callback_data="adm_alerts_read_all")],
        [InlineKeyboardButton("🔄 Обновить", callback_data="adm_alerts")],
        [InlineKeyboardButton("◀️ Назад", callback_data="adm_main")]
    ]

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))


@admin_only
async def read_all_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Прочитать все алерты"""
    query = update.callback_query
    await db.mark_all_alerts_read()
    await query.answer("✅ Все алерты прочитаны")
    await alerts_list(update, context)


# ==================== АНАЛИТИКА ====================

@admin_only
async def analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Аналитика"""
    query = update.callback_query
    await query.answer()

    stats = await db.get_detailed_stats()

    text = "📊 <b>АНАЛИТИКА</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    # Пользователи
    text += "👥 <b>ПОЛЬЗОВАТЕЛИ</b>\n"
    text += f"  Всего: {stats['total_users']}\n"
    text += f"  Новых сегодня: +{stats['new_today']}\n"
    text += f"  Активных (24ч): {stats['active_today']}\n"
    text += f"  Активных (7д): {stats['active_week']}\n\n"

    # Заказы
    text += "📦 <b>ЗАКАЗЫ</b>\n"
    text += f"  Всего: {stats['total_orders']}\n"
    text += f"  Новых: {stats['new_orders']}\n"
    text += f"  В работе: {stats['in_progress']}\n"
    text += f"  Выполнено: {stats['completed']}\n\n"

    # Деньги
    text += "💰 <b>ФИНАНСЫ</b>\n"
    text += f"  Всего заработано: {stats['total_revenue']:,}₽\n"
    text += f"  Сегодня: {stats['today_revenue']:,}₽\n"
    text += f"  Ожидает оплаты: {stats['pending_revenue']:,}₽\n\n"

    # Конверсия
    if stats['total_users'] > 0:
        conversion = round(stats['total_orders'] / stats['total_users'] * 100, 1)
        text += f"📈 <b>Конверсия:</b> {conversion}%\n"

    if stats['total_orders'] > 0:
        avg_check = round(stats['total_revenue'] / max(stats['completed'], 1))
        text += f"🧾 <b>Средний чек:</b> {avg_check}₽\n"

    keyboard = [
        [InlineKeyboardButton("📈 Воронка", callback_data="adm_funnel")],
        [InlineKeyboardButton("🔥 Горячие лиды", callback_data="adm_hot_leads")],
        [InlineKeyboardButton("◀️ Назад", callback_data="adm_main")]
    ]

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))


# ==================== ГОРЯЧИЕ ЛИДЫ ====================

@admin_only
async def hot_leads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Горячие лиды — смотрели прайс, но не заказали"""
    query = update.callback_query
    await query.answer()

    leads = await db.get_hot_leads()

    text = "🔥 <b>ГОРЯЧИЕ ЛИДЫ</b>\n"
    text += "<i>Смотрели прайс, но не заказали</i>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    if leads:
        for l in leads:
            name = escape(l.get('full_name', 'Без имени')[:20])
            views = l.get('price_views', 0)
            last_seen = str(l.get('last_seen', ''))[:16]
            text += f"👤 <b>{name}</b>\n"
            text += f"   👀 Смотрел прайс: {views} раз\n"
            text += f"   🕐 Был: {last_seen}\n\n"
    else:
        text += "<i>Нет горячих лидов</i>"

    keyboard = []
    for l in leads[:5]:
        name = (l.get('full_name') or 'Без имени')[:15]
        keyboard.append([
            InlineKeyboardButton(f"✉️ Написать {name}",
                               callback_data=f"adm_dm_{l['user_id']}")
        ])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="adm_main")])

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))


# ==================== БРОШЕННЫЕ КОРЗИНЫ ====================

@admin_only
async def abandoned_carts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Брошенные корзины"""
    query = update.callback_query
    await query.answer()

    carts = await db.get_abandoned_carts(hours=48)

    text = "🛒 <b>БРОШЕННЫЕ КОРЗИНЫ</b>\n"
    text += "<i>За последние 48 часов</i>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    if carts:
        for c in carts:
            name = escape(c.get('full_name', 'Без имени')[:20])
            stage = c.get('stage', 'неизвестно')
            time = str(c.get('created_at', ''))[:16]
            text += f"👤 <b>{name}</b>\n"
            text += f"   📍 Этап: {stage}\n"
            text += f"   🕐 Время: {time}\n\n"
    else:
        text += "<i>Нет брошенных корзин</i> ✨"

    keyboard = []
    for c in carts[:5]:
        name = (c.get('full_name') or 'Без имени')[:15]
        keyboard.append([
            InlineKeyboardButton(f"✉️ Дожать {name}",
                               callback_data=f"adm_dm_{c['user_id']}")
        ])

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="adm_main")])

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))


# ==================== ЖИВОЙ ЛОГ ====================

@admin_only
async def live_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Живой лог всех действий"""
    query = update.callback_query
    await query.answer()

    actions = await db.get_recent_actions(limit=25)

    text = "📜 <b>ЖИВОЙ ЛОГ</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    if actions:
        for a in actions:
            time = str(a.get('created_at', ''))[-8:-3]
            name = escape((a.get('full_name') or 'Аноним')[:12])
            action = escape((a.get('action') or '')[:25])
            text += f"<code>{time}</code> <b>{name}</b>\n"
            text += f"        {action}\n"
    else:
        text += "<i>Нет данных</i>"

    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="adm_live_log")],
        [InlineKeyboardButton("◀️ Назад", callback_data="adm_main")]
    ]

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(keyboard))


# ==================== ПОИСК ====================

@admin_only
async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало поиска"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "🔍 <b>ПОИСК</b>\n\n"
        "Введите имя, username или ID пользователя:",
        parse_mode=ParseMode.HTML
    )

    return SEARCH_USER


async def search_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка поиска"""
    query_text = update.message.text

    users = await db.search_users(query_text)

    if not users:
        await update.message.reply_text(
            "❌ Ничего не найдено\n\n/admin — вернуться в панель"
        )
        return ConversationHandler.END

    text = f"🔍 <b>Результаты поиска:</b> {query_text}\n\n"

    keyboard = []
    for u in users[:10]:
        name = escape(u.get('full_name', 'Без имени')[:25])
        text += f"• {name} (ID: {u['user_id']})\n"
        keyboard.append([
            InlineKeyboardButton(f"👤 {name}",
                               callback_data=f"adm_user_{u['user_id']}")
        ])

    keyboard.append([InlineKeyboardButton("◀️ В админку", callback_data="adm_main")])

    await update.message.reply_text(text, parse_mode=ParseMode.HTML,
                                    reply_markup=InlineKeyboardMarkup(keyboard))

    return ConversationHandler.END


# ==================== РАССЫЛКА ====================

@admin_only
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало рассылки"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "📣 <b>РАССЫЛКА</b>\n\n"
        "Отправьте сообщение для рассылки всем пользователям.\n"
        "Можно отправить текст, фото или документ.\n\n"
        "/cancel — отменить",
        parse_mode=ParseMode.HTML
    )

    return BROADCAST_MSG


async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка рассылки"""
    users = await db.get_all_users(limit=10000)

    sent = 0
    failed = 0

    status_msg = await update.message.reply_text("📣 Начинаю рассылку...")

    for user in users:
        try:
            if update.message.photo:
                await context.bot.send_photo(
                    user['user_id'],
                    update.message.photo[-1].file_id,
                    caption=update.message.caption
                )
            elif update.message.document:
                await context.bot.send_document(
                    user['user_id'],
                    update.message.document.file_id,
                    caption=update.message.caption
                )
            else:
                await context.bot.send_message(
                    user['user_id'],
                    update.message.text
                )
            sent += 1
        except Exception:
            failed += 1

        # Обновляем статус каждые 10 юзеров
        if (sent + failed) % 10 == 0:
            await status_msg.edit_text(f"📣 Отправлено: {sent} | Ошибок: {failed}")

    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📨 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}",
        parse_mode=ParseMode.HTML
    )

    return ConversationHandler.END


# ==================== DM ПОЛЬЗОВАТЕЛЮ ====================

@admin_only
async def dm_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Написать пользователю напрямую"""
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split("_")[-1])
    context.user_data['dm_target'] = user_id

    user = await db.get_user(user_id)
    name = user.get('full_name', 'Пользователь') if user else 'Пользователь'

    await query.edit_message_text(
        f"✉️ <b>Написать пользователю</b>\n"
        f"👤 {escape(name)} (ID: {user_id})\n\n"
        f"Отправьте сообщение:",
        parse_mode=ParseMode.HTML
    )

    return BROADCAST_MSG  # Используем тот же state


async def dm_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить DM"""
    user_id = context.user_data.get('dm_target')

    if not user_id:
        await update.message.reply_text("❌ Ошибка: не выбран получатель")
        return ConversationHandler.END

    try:
        if update.message.photo:
            await context.bot.send_photo(
                user_id,
                update.message.photo[-1].file_id,
                caption=update.message.caption
            )
        elif update.message.document:
            await context.bot.send_document(
                user_id,
                update.message.document.file_id,
                caption=update.message.caption
            )
        else:
            await context.bot.send_message(user_id, update.message.text)

        await update.message.reply_text("✅ Сообщение отправлено!")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена операции"""
    await update.message.reply_text("❌ Отменено\n\n/admin — вернуться в панель")
    return ConversationHandler.END


# ==================== НАСТРОЙКА ХЕНДЛЕРОВ ====================

def setup(app):
    """Подключение всех хендлеров админки"""

    # Команда /admin
    app.add_handler(CommandHandler("admin", admin_panel))

    # Callback handlers
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^adm_main$"))
    app.add_handler(CallbackQueryHandler(refresh_panel, pattern="^adm_refresh$"))

    # Заказы
    app.add_handler(CallbackQueryHandler(orders_list, pattern="^adm_orders"))
    app.add_handler(CallbackQueryHandler(order_detail, pattern="^adm_order_\\d+$"))
    app.add_handler(CallbackQueryHandler(change_status, pattern="^adm_status_\\d+$"))
    app.add_handler(CallbackQueryHandler(set_status, pattern="^adm_setstatus_"))

    # Пользователи
    app.add_handler(CallbackQueryHandler(users_list, pattern="^adm_users"))
    app.add_handler(CallbackQueryHandler(user_profile, pattern="^adm_user_\\d+$"))
    app.add_handler(CallbackQueryHandler(user_actions_log, pattern="^adm_actions_\\d+$"))
    app.add_handler(CallbackQueryHandler(toggle_ban, pattern="^adm_toggleban_\\d+$"))

    # Алерты
    app.add_handler(CallbackQueryHandler(alerts_list, pattern="^adm_alerts$"))
    app.add_handler(CallbackQueryHandler(read_all_alerts, pattern="^adm_alerts_read_all$"))

    # Аналитика
    app.add_handler(CallbackQueryHandler(analytics, pattern="^adm_analytics$"))
    app.add_handler(CallbackQueryHandler(hot_leads, pattern="^adm_hot_leads$"))
    app.add_handler(CallbackQueryHandler(abandoned_carts, pattern="^adm_abandoned$"))
    app.add_handler(CallbackQueryHandler(live_log, pattern="^adm_live_log$"))

    # Поиск (ConversationHandler)
    search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(search_start, pattern="^adm_search$")],
        states={
            SEARCH_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_process)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    app.add_handler(search_conv)

    # Рассылка (ConversationHandler)
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_start, pattern="^adm_broadcast$")],
        states={
            BROADCAST_MSG: [MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_send)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    app.add_handler(broadcast_conv)

    # DM пользователю (ConversationHandler)
    dm_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(dm_start, pattern="^adm_dm_\\d+$")],
        states={
            BROADCAST_MSG: [MessageHandler(filters.ALL & ~filters.COMMAND, dm_send)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    app.add_handler(dm_conv)

    logger.info("✅ Admin handlers подключены")
