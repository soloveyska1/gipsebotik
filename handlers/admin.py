"""
Супер-админка для управления ботом.
Вход: /admin_<секретный_код>
"""
import asyncio
import logging
from datetime import datetime
from html import escape

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from config import (
    ADMIN_IDS, ADMIN_USERNAMES, ADMIN_SECRET_CODE,
    MAX_ADMIN_ATTEMPTS, ADMIN_BAN_TIME, LOG_CHANNEL_ID, SERVICES
)
from database import core as db
from keyboards import admin as kb

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
(
    WAITING_SEARCH,
    WAITING_BALANCE_AMOUNT,
    WAITING_NOTE,
    WAITING_CHAT_MESSAGE,
    WAITING_BROADCAST_TEXT,
    WAITING_PROMO_CODE,
    WAITING_PROMO_AMOUNT,
    WAITING_ORDER_PRICE,
    WAITING_FILE,
) = range(9)


# ========================================
# === БЕЗОПАСНОСТЬ ===
# ========================================

def is_admin(user) -> bool:
    """Проверка: является ли пользователь админом (двойная проверка)."""
    if user.id not in ADMIN_IDS:
        return False
    # Дополнительная проверка username (если настроено)
    if ADMIN_USERNAMES and user.username:
        return user.username.lower() in [u.lower() for u in ADMIN_USERNAMES]
    return True


async def check_admin_ban(user_id) -> bool:
    """Проверить, заблокирован ли пользователь за попытки взлома."""
    ban = await db.get_admin_ban(user_id)
    if ban and ban.get("banned_until"):
        try:
            banned_until = datetime.fromisoformat(ban["banned_until"])
            if datetime.now() < banned_until:
                return True
        except:
            pass
    return False


async def notify_security_event(context, user, action, success=False):
    """Отправить уведомление о событии безопасности в лог-канал."""
    if not LOG_CHANNEL_ID:
        return

    if await db.get_notification_setting("security"):
        emoji = "✅" if success else "🚫"
        status = "УСПЕШНЫЙ ВХОД" if success else "ПОПЫТКА ВХОДА"

        text = (
            f"{emoji} <b>{status} В АДМИНКУ</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👤 <a href=\"tg://user?id={user.id}\">{escape(user.full_name)}</a>\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"📱 Username: @{user.username or 'нет'}\n"
            f"📍 Действие: {action}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )

        try:
            await context.bot.send_message(
                LOG_CHANNEL_ID,
                text,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления безопасности: {e}")


# ========================================
# === ВХОД В АДМИНКУ ===
# ========================================

async def admin_secret_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Секретная команда входа в админку: /admin_<код>"""
    user = update.effective_user
    command = update.message.text

    # Логируем попытку
    await db.log_admin_access(user.id, user.username, user.full_name, command, success=False)

    # Проверяем бан
    if await check_admin_ban(user.id):
        # Молча игнорируем — "команда не найдена"
        return

    # Проверяем код
    expected_command = f"/admin_{ADMIN_SECRET_CODE}"
    if command.lower() != expected_command.lower():
        # Неверный код — добавляем попытку
        banned = await db.add_admin_attempt(user.id, MAX_ADMIN_ATTEMPTS, ADMIN_BAN_TIME)
        await notify_security_event(context, user, f"Неверный код: {command}", success=False)

        if banned:
            await notify_security_event(context, user, "ЗАБЛОКИРОВАН за попытки взлома", success=False)
        return

    # Проверяем права
    if not is_admin(user):
        await db.add_admin_attempt(user.id, MAX_ADMIN_ATTEMPTS, ADMIN_BAN_TIME)
        await notify_security_event(context, user, "Нет прав доступа", success=False)
        return

    # Успешный вход!
    await db.reset_admin_attempts(user.id)
    await db.log_admin_access(user.id, user.username, user.full_name, "Успешный вход", success=True)
    await notify_security_event(context, user, "Вход в админку", success=True)

    # Показываем главную панель
    await show_admin_panel(update, context)


async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главная панель админки с дашбордом."""
    user = update.effective_user

    if not is_admin(user):
        return

    # Получаем статистику
    stats = await db.get_extended_stats()

    # Формируем дашборд
    text = (
        f"🔐 <b>ПАНЕЛЬ УПРАВЛЕНИЯ САЛУНОМ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 <b>Пользователи:</b> {stats['total_users']} "
        f"<i>(+{stats['today_users']} сегодня)</i>\n\n"
        f"📋 <b>Заказы:</b> {stats['total_orders']}\n"
        f"├ 🟡 На проверке: {stats['checking_orders']}\n"
        f"├ ⚙️ В работе: {stats['work_orders']}\n"
        f"└ ✅ Выполнено: {stats['done_orders']}\n\n"
        f"💰 <b>Оборот:</b> {stats['total_revenue']:,}₽\n"
        f"├ За месяц: {stats['month_revenue']:,}₽\n"
        f"├ За неделю: {stats['week_revenue']:,}₽\n"
        f"└ Сегодня: {stats['today_revenue']:,}₽\n\n"
        f"⭐ <b>Средний чек:</b> {int(stats['avg_order']):,}₽\n"
        f"🎯 <b>Конверсия:</b> {stats['conversion']}%\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Обновлено: {datetime.now().strftime('%H:%M:%S')}</i>"
    )

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(
            text,
            reply_markup=kb.admin_main_kb(),
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=kb.admin_main_kb(),
            parse_mode=ParseMode.HTML
        )


async def admin_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обновить дашборд."""
    await show_admin_panel(update, context)


# ========================================
# === КЛИЕНТЫ ===
# ========================================

async def show_clients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список клиентов."""
    query = update.callback_query
    await query.answer()

    page = context.user_data.get("cli_page", 1)
    filter_type = context.user_data.get("cli_filter", None)

    result = await db.get_users_paginated(page=page, per_page=8, filter_type=filter_type)

    text = f"👥 <b>КЛИЕНТЫ</b> ({result['total']})\n"
    text += "━━━━━━━━━━━━━━━\n\n"

    for u in result["users"]:
        banned = "🚫" if u["is_banned"] else ""
        orders = f"📦{u['orders_count']}" if u["orders_count"] > 0 else ""
        username = f"@{u['username']}" if u["username"] else ""

        text += (
            f"{banned}👤 <a href=\"tg://user?id={u['user_id']}\">{escape(u['full_name'] or 'Без имени')}</a> "
            f"{username}\n"
            f"    💰 {u['balance']}₽ | 💸 {u['total_spent']}₽ {orders}\n"
            f"    <code>/adm_cli_{u['user_id']}</code>\n\n"
        )

    await query.message.edit_text(
        text,
        reply_markup=kb.clients_list_kb(page, result["total_pages"], filter_type),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )


async def clients_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Фильтр клиентов."""
    query = update.callback_query
    filter_type = query.data.split("_")[-1]

    context.user_data["cli_filter"] = None if filter_type == "all" else filter_type
    context.user_data["cli_page"] = 1

    await show_clients(update, context)


async def clients_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пагинация клиентов."""
    query = update.callback_query
    page = int(query.data.split("_")[-1])

    context.user_data["cli_page"] = page
    await show_clients(update, context)


async def show_client_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Карточка клиента."""
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split("_")[-1])
    user = await db.get_user(user_id)

    if not user:
        await query.answer("Пользователь не найден", show_alert=True)
        return

    # Определяем ранг
    from handlers.client import get_user_rank
    rank = get_user_rank(user['total_spent'], user['orders_count'])

    # Проверяем, отслеживается ли
    watched = await db.is_user_watched(user_id)
    is_watched = len(watched) > 0

    # Получаем заметку
    note = await db.get_admin_note(user_id)
    note_text = f"\n📝 <b>Заметка:</b> <i>{escape(note['note'])}</i>" if note else ""

    # Получаем реферера
    referrer_text = ""
    if user['referrer_id']:
        referrer = await db.get_user(user['referrer_id'])
        if referrer:
            referrer_text = f"\n🔗 Реферер: <a href=\"tg://user?id={referrer['user_id']}\">{escape(referrer['full_name'] or 'Неизвестно')}</a>"

    username = f"@{user['username']}" if user['username'] else "не указан"

    text = (
        f"👤 <b>КЛИЕНТ #{user['user_id']}</b>\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"📱 Telegram: <a href=\"tg://user?id={user['user_id']}\">{username}</a>\n"
        f"📝 Имя: {escape(user['full_name'] or 'Не указано')}\n"
        f"📅 Регистрация: {user['joined_at'][:10] if user['joined_at'] else 'Неизвестно'}\n"
        f"🎖 Ранг: {rank}\n"
        f"{referrer_text}\n\n"
        f"💰 <b>ФИНАНСЫ:</b>\n"
        f"├ Баланс: <b>{user['balance']}₽</b>\n"
        f"├ Всего потратил: {user['total_spent']}₽\n"
        f"└ Заказов: {user['orders_count']}\n\n"
        f"📊 <b>СТАТУС:</b>\n"
        f"├ Правила: {'✅ Принял' if user['rules_accepted'] else '❌ Не принял'}\n"
        f"├ Бан: {'🚫 Да' if user['is_banned'] else '✅ Нет'}\n"
        f"└ Мониторинг: {'👁 Включен' if is_watched else '➖ Выключен'}"
        f"{note_text}"
    )

    await query.message.edit_text(
        text,
        reply_markup=kb.client_card_kb(user_id, user['is_banned'], is_watched),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )


async def toggle_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Забанить/разбанить пользователя."""
    query = update.callback_query
    user_id = int(query.data.split("_")[-1])

    user = await db.get_user(user_id)
    if not user:
        await query.answer("Пользователь не найден", show_alert=True)
        return

    if user['is_banned']:
        await db.unban_user(user_id)
        await query.answer("✅ Пользователь разбанен", show_alert=True)
    else:
        await db.ban_user(user_id)
        await query.answer("🚫 Пользователь забанен", show_alert=True)

    # Обновляем карточку
    await show_client_card(update, context)


async def toggle_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Включить/выключить мониторинг пользователя."""
    query = update.callback_query
    admin_id = query.from_user.id
    user_id = int(query.data.split("_")[-1])

    watched = await db.is_user_watched(user_id)

    if admin_id in watched:
        await db.remove_watcher(admin_id, user_id)
        await query.answer("👁 Мониторинг выключен", show_alert=True)
    else:
        await db.add_watcher(admin_id, user_id)
        await query.answer("👁 Мониторинг включен — все действия будут приходить вам", show_alert=True)

    await show_client_card(update, context)


async def ask_balance_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос суммы для изменения баланса."""
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split("_")[-1])
    context.user_data["balance_user_id"] = user_id

    await query.message.edit_text(
        "💰 <b>Изменение баланса</b>\n\n"
        "Введите сумму (положительную для начисления, отрицательную для списания):\n"
        "Например: <code>100</code> или <code>-50</code>",
        reply_markup=kb.cancel_kb(),
        parse_mode=ParseMode.HTML
    )

    return WAITING_BALANCE_AMOUNT


async def process_balance_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка изменения баланса."""
    try:
        amount = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат. Введите число:",
            reply_markup=kb.cancel_kb()
        )
        return WAITING_BALANCE_AMOUNT

    user_id = context.user_data.get("balance_user_id")
    if not user_id:
        return ConversationHandler.END

    reason = "Начисление админом" if amount > 0 else "Списание админом"
    await db.add_balance(user_id, amount, reason)

    # Уведомляем в лог
    admin = update.effective_user
    if LOG_CHANNEL_ID and await db.get_notification_setting("messages"):
        user = await db.get_user(user_id)
        sign = "+" if amount > 0 else ""
        text = (
            f"💰 <b>БАЛАНС ИЗМЕНЕН</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👤 <a href=\"tg://user?id={user_id}\">{escape(user['full_name'] if user else 'Неизвестно')}</a>\n"
            f"💵 {sign}{amount}₽\n"
            f"📝 {reason}\n"
            f"👨‍💼 Админ: {escape(admin.full_name)}"
        )
        try:
            await context.bot.send_message(LOG_CHANNEL_ID, text, parse_mode=ParseMode.HTML)
        except:
            pass

    await update.message.reply_text(
        f"✅ Баланс изменен на {amount}₽",
        reply_markup=kb.back_kb(f"adm_client_{user_id}")
    )

    return ConversationHandler.END


async def ask_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос заметки о клиенте."""
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split("_")[-1])
    context.user_data["note_user_id"] = user_id

    # Получаем текущую заметку
    note = await db.get_admin_note(user_id)
    current = f"\n\nТекущая заметка: <i>{escape(note['note'])}</i>" if note else ""

    await query.message.edit_text(
        f"📝 <b>Заметка о клиенте</b>{current}\n\n"
        "Введите новую заметку:",
        reply_markup=kb.cancel_kb(),
        parse_mode=ParseMode.HTML
    )

    return WAITING_NOTE


async def process_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение заметки."""
    note_text = update.message.text.strip()
    user_id = context.user_data.get("note_user_id")
    admin_id = update.effective_user.id

    if not user_id:
        return ConversationHandler.END

    await db.set_admin_note(user_id, note_text, admin_id)

    await update.message.reply_text(
        "✅ Заметка сохранена",
        reply_markup=kb.back_kb(f"adm_client_{user_id}")
    )

    return ConversationHandler.END


# ========================================
# === ЗАКАЗЫ ===
# ========================================

async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список заказов."""
    query = update.callback_query
    await query.answer()

    page = context.user_data.get("ord_page", 1)
    status_filter = context.user_data.get("ord_filter", None)

    result = await db.get_orders_paginated(page=page, per_page=8, status_filter=status_filter)

    status_emoji = {"checking": "🟡", "work": "⚙️", "done": "✅", "cancel": "❌"}

    text = f"📋 <b>ЗАКАЗЫ</b> ({result['total']})\n"
    text += "━━━━━━━━━━━━━━━\n\n"

    for o in result["orders"]:
        emoji = status_emoji.get(o["status"], "📦")
        username = f"@{o['username']}" if o["username"] else ""
        short_topic = (o["topic"] or "Без темы")[:30]
        if len(o["topic"] or "") > 30:
            short_topic += "..."

        text += (
            f"{emoji} <b>#{o['id']}</b> | {o['service_type'] or 'Услуга'}\n"
            f"    👤 {username} | 💰 {o['price']}₽\n"
            f"    📝 {escape(short_topic)}\n"
            f"    <code>/adm_ord_{o['id']}</code>\n\n"
        )

    await query.message.edit_text(
        text,
        reply_markup=kb.orders_list_kb(page, result["total_pages"], status_filter),
        parse_mode=ParseMode.HTML
    )


async def orders_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Фильтр заказов."""
    query = update.callback_query
    status = query.data.split("_")[-1]

    context.user_data["ord_filter"] = None if status == "all" else status
    context.user_data["ord_page"] = 1

    await show_orders(update, context)


async def orders_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пагинация заказов."""
    query = update.callback_query
    page = int(query.data.split("_")[-1])

    context.user_data["ord_page"] = page
    await show_orders(update, context)


async def show_order_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Карточка заказа."""
    query = update.callback_query
    await query.answer()

    order_id = int(query.data.split("_")[-1])
    order = await db.get_full_order(order_id)

    if not order:
        await query.answer("Заказ не найден", show_alert=True)
        return

    status_map = {
        "checking": "🟡 На проверке",
        "work": "⚙️ В работе",
        "done": "✅ Готов",
        "cancel": "❌ Отменён"
    }

    username = f"@{order['username']}" if order.get('username') else "нет"

    # Дополнительные услуги
    extras = []
    if order.get('speech'):
        extras.append("🎤 Речь")
    if order.get('pres'):
        extras.append("📊 Презентация")
    if order.get('vip'):
        extras.append("👑 VIP")
    extras_text = " | ".join(extras) if extras else "нет"

    text = (
        f"📋 <b>ЗАКАЗ #{order['id']}</b>\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"👤 Клиент: <a href=\"tg://user?id={order['user_id']}\">{escape(order['full_name'] or 'Неизвестно')}</a> ({username})\n"
        f"📱 <code>/adm_cli_{order['user_id']}</code>\n\n"
        f"📚 <b>Тип:</b> {order['service_type'] or 'Не указан'}\n"
        f"📝 <b>Тема:</b> {escape(order['topic'] or 'Не указана')}\n"
        f"📅 <b>Дедлайн:</b> {order['deadline'] or 'Не указан'}\n\n"
        f"💰 <b>Цена:</b> {order['price']}₽\n"
        f"🎁 <b>Доп. услуги:</b> {extras_text}\n\n"
        f"📊 <b>Статус:</b> {status_map.get(order['status'], order['status'])}\n"
        f"📅 <b>Создан:</b> {order['created_at'][:16] if order['created_at'] else 'Неизвестно'}"
    )

    await query.message.edit_text(
        text,
        reply_markup=kb.order_card_kb(order_id, order['status']),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )


async def change_order_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменение статуса заказа."""
    query = update.callback_query
    parts = query.data.split("_")
    order_id = int(parts[-2])
    new_status = parts[-1]

    await db.update_order_status(order_id, new_status)

    status_names = {"checking": "На проверке", "work": "В работе", "done": "Готов", "cancel": "Отменён"}
    await query.answer(f"✅ Статус изменён на: {status_names.get(new_status, new_status)}", show_alert=True)

    # Уведомляем клиента
    order = await db.get_full_order(order_id)
    if order:
        status_emoji = {"checking": "🟡", "work": "⚙️", "done": "✅", "cancel": "❌"}
        client_text = (
            f"{status_emoji.get(new_status, '📋')} <b>Статус заказа #{order_id} изменён</b>\n\n"
            f"Новый статус: <b>{status_names.get(new_status, new_status)}</b>"
        )
        try:
            await context.bot.send_message(order['user_id'], client_text, parse_mode=ParseMode.HTML)
        except:
            pass

    await show_order_card(update, context)


# ========================================
# === ФИНАНСЫ ===
# ========================================

async def show_finance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Финансовая панель."""
    query = update.callback_query
    await query.answer()

    stats = await db.get_extended_stats()

    text = (
        f"💰 <b>ФИНАНСЫ</b>\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>ОБЩАЯ СТАТИСТИКА:</b>\n"
        f"├ Всего заработано: <b>{stats['total_revenue']:,}₽</b>\n"
        f"├ За месяц: {stats['month_revenue']:,}₽\n"
        f"├ За неделю: {stats['week_revenue']:,}₽\n"
        f"└ За сегодня: {stats['today_revenue']:,}₽\n\n"
        f"⭐ <b>Средний чек:</b> {int(stats['avg_order']):,}₽\n\n"
        f"💎 <b>БОНУСЫ НА БАЛАНСАХ:</b> {stats['total_bonuses']:,}₽"
    )

    await query.message.edit_text(
        text,
        reply_markup=kb.finance_kb(),
        parse_mode=ParseMode.HTML
    )


async def show_finance_by_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выручка по услугам."""
    query = update.callback_query
    await query.answer()

    revenue = await db.get_revenue_by_service()

    text = "📈 <b>ВЫРУЧКА ПО УСЛУГАМ</b>\n━━━━━━━━━━━━━━━\n\n"

    for item in revenue:
        service_name = SERVICES.get(item['service_type'], {}).get('name', item['service_type'] or 'Неизвестно')
        text += f"├ {service_name}\n"
        text += f"│   {item['count']} шт. — {item['revenue']:,}₽\n"

    await query.message.edit_text(
        text,
        reply_markup=kb.back_kb("adm_finance"),
        parse_mode=ParseMode.HTML
    )


# ========================================
# === АНАЛИТИКА ===
# ========================================

async def show_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Аналитика."""
    query = update.callback_query
    await query.answer()

    stats = await db.get_extended_stats()

    text = (
        f"📊 <b>АНАЛИТИКА</b>\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"🎯 <b>Конверсия:</b> {stats['conversion']}%\n"
        f"   (пользователей с заказами / всего)\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"├ Всего: {stats['total_users']}\n"
        f"├ За неделю: +{stats['week_users']}\n"
        f"└ Сегодня: +{stats['today_users']}\n\n"
        f"📦 <b>Заказы:</b>\n"
        f"├ Всего: {stats['total_orders']}\n"
        f"├ Активных: {stats['checking_orders'] + stats['work_orders']}\n"
        f"└ Выполнено: {stats['done_orders']}"
    )

    await query.message.edit_text(
        text,
        reply_markup=kb.analytics_kb(),
        parse_mode=ParseMode.HTML
    )


async def show_referral_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Топ рефереров."""
    query = update.callback_query
    await query.answer()

    referrals = await db.get_referral_stats()

    text = "👥 <b>ТОП РЕФЕРЕРОВ</b>\n━━━━━━━━━━━━━━━\n\n"

    if not referrals:
        text += "<i>Пока нет рефералов</i>"
    else:
        for i, r in enumerate(referrals, 1):
            username = f"@{r['username']}" if r['username'] else ""
            text += f"{i}. {escape(r['full_name'])} {username}\n"
            text += f"    Привел: {r['referrals_count']} чел.\n\n"

    await query.message.edit_text(
        text,
        reply_markup=kb.back_kb("adm_analytics"),
        parse_mode=ParseMode.HTML
    )


# ========================================
# === РАССЫЛКА ===
# ========================================

async def show_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню рассылки."""
    query = update.callback_query
    await query.answer()

    # Получаем количество пользователей для каждого фильтра
    all_users = await db.get_users_for_broadcast("all")
    with_orders = await db.get_users_for_broadcast("with_orders")
    without_orders = await db.get_users_for_broadcast("without_orders")
    vip = await db.get_users_for_broadcast("vip")

    text = (
        f"📢 <b>РАССЫЛКА</b>\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"Выберите аудиторию:\n\n"
        f"📢 Всем: {len(all_users)} чел.\n"
        f"🛒 С заказами: {len(with_orders)} чел.\n"
        f"🆕 Без заказов: {len(without_orders)} чел.\n"
        f"👑 VIP (10000₽+): {len(vip)} чел."
    )

    await query.message.edit_text(
        text,
        reply_markup=kb.broadcast_kb(),
        parse_mode=ParseMode.HTML
    )


async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания рассылки."""
    query = update.callback_query
    await query.answer()

    filter_type = query.data.split("_")[-1]
    context.user_data["bc_filter"] = filter_type

    await query.message.edit_text(
        "📢 <b>Создание рассылки</b>\n\n"
        "Отправьте текст сообщения для рассылки.\n"
        "Можно использовать HTML-форматирование.",
        reply_markup=kb.cancel_kb(),
        parse_mode=ParseMode.HTML
    )

    return WAITING_BROADCAST_TEXT


async def process_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста рассылки."""
    text = update.message.text
    filter_type = context.user_data.get("bc_filter", "all")

    context.user_data["bc_text"] = text

    users = await db.get_users_for_broadcast(filter_type)

    await update.message.reply_text(
        f"📢 <b>Подтверждение рассылки</b>\n\n"
        f"Текст:\n{text}\n\n"
        f"Получателей: {len(users)} чел.\n\n"
        f"Отправить?",
        reply_markup=kb.broadcast_confirm_kb(filter_type, len(users)),
        parse_mode=ParseMode.HTML
    )

    return ConversationHandler.END


async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка рассылки."""
    query = update.callback_query
    await query.answer("📤 Начинаю рассылку...")

    filter_type = query.data.split("_")[-1]
    text = context.user_data.get("bc_text", "")

    if not text:
        await query.answer("❌ Текст рассылки не найден", show_alert=True)
        return

    users = await db.get_users_for_broadcast(filter_type)
    admin_id = query.from_user.id

    # Создаем запись о рассылке
    broadcast_id = await db.create_broadcast(text, None, filter_type, admin_id)

    sent = 0
    failed = 0

    for user_id in users:
        try:
            await context.bot.send_message(user_id, text, parse_mode=ParseMode.HTML)
            sent += 1
            await asyncio.sleep(0.05)  # Небольшая задержка
        except Exception as e:
            failed += 1
            logger.debug(f"Не удалось отправить {user_id}: {e}")

    await db.update_broadcast_count(broadcast_id, sent)

    await query.message.edit_text(
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}",
        reply_markup=kb.back_kb("adm_broadcast"),
        parse_mode=ParseMode.HTML
    )


# ========================================
# === ПРОМОКОДЫ ===
# ========================================

async def show_promos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню промокодов."""
    query = update.callback_query
    await query.answer()

    await query.message.edit_text(
        "🎁 <b>ПРОМОКОДЫ</b>\n━━━━━━━━━━━━━━━\n\n"
        "Управление промокодами:",
        reply_markup=kb.promos_kb(),
        parse_mode=ParseMode.HTML
    )


async def show_promo_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика промокодов."""
    query = update.callback_query
    await query.answer()

    promos = await db.get_promo_stats()

    text = "🎁 <b>ПРОМОКОДЫ</b>\n━━━━━━━━━━━━━━━\n\n"

    if not promos:
        text += "<i>Промокодов пока нет</i>"
    else:
        for p in promos:
            status = "🟢" if p['is_active'] else "🔴"
            bonus = f"+{p['bonus_amount']}₽" if p['bonus_amount'] else ""
            discount = f"-{p['discount_percent']}%" if p['discount_percent'] else ""
            value = bonus or discount or "?"

            text += (
                f"{status} <code>{p['code']}</code> — {value}\n"
                f"    Использован: {p['current_uses']}/{p['max_uses']}\n\n"
            )

    await query.message.edit_text(
        text,
        reply_markup=kb.back_kb("adm_promos"),
        parse_mode=ParseMode.HTML
    )


async def start_promo_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания промокода."""
    query = update.callback_query
    await query.answer()

    await query.message.edit_text(
        "🎁 <b>Создание промокода</b>\n\n"
        "Введите код (латиница, цифры):",
        reply_markup=kb.cancel_kb(),
        parse_mode=ParseMode.HTML
    )

    return WAITING_PROMO_CODE


async def process_promo_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кода промокода."""
    code = update.message.text.strip().upper()
    context.user_data["new_promo_code"] = code

    await update.message.reply_text(
        f"Код: <code>{code}</code>\n\n"
        "Теперь введите бонус в рублях:\n"
        "Например: <code>50</code>",
        reply_markup=kb.cancel_kb(),
        parse_mode=ParseMode.HTML
    )

    return WAITING_PROMO_AMOUNT


async def process_promo_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка суммы промокода."""
    try:
        amount = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Введите число:", reply_markup=kb.cancel_kb())
        return WAITING_PROMO_AMOUNT

    code = context.user_data.get("new_promo_code")
    if not code:
        return ConversationHandler.END

    await db.create_promo_code(code, discount_percent=0, bonus_amount=amount, max_uses=1000)

    await update.message.reply_text(
        f"✅ Промокод <code>{code}</code> создан!\n"
        f"Бонус: +{amount}₽",
        reply_markup=kb.back_kb("adm_promos"),
        parse_mode=ParseMode.HTML
    )

    return ConversationHandler.END


async def toggle_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Включить/выключить промокод."""
    query = update.callback_query
    code = query.data.split("_")[-1]

    promos = await db.get_promo_stats()
    promo = next((p for p in promos if p['code'] == code), None)

    if promo:
        if promo['is_active']:
            await db.deactivate_promo_code(code)
            await query.answer(f"🔴 Промокод {code} выключен", show_alert=True)
        else:
            await db.activate_promo_code(code)
            await query.answer(f"🟢 Промокод {code} включен", show_alert=True)

    await show_promo_stats(update, context)


# ========================================
# === НАСТРОЙКИ УВЕДОМЛЕНИЙ ===
# ========================================

async def show_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройки уведомлений."""
    query = update.callback_query
    await query.answer()

    settings = await db.get_all_notification_settings()

    await query.message.edit_text(
        "🔔 <b>НАСТРОЙКИ УВЕДОМЛЕНИЙ</b>\n━━━━━━━━━━━━━━━\n\n"
        "Выберите, какие уведомления получать в канал:",
        reply_markup=kb.notifications_kb(settings),
        parse_mode=ParseMode.HTML
    )


async def toggle_notification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключение настройки уведомления."""
    query = update.callback_query
    key = query.data.replace("adm_notif_toggle_", "")

    current = await db.get_notification_setting(key)
    await db.set_notification_setting(key, not current)

    await query.answer(f"{'🔔 Включено' if not current else '🔕 Выключено'}")
    await show_notifications(update, context)


# ========================================
# === ЧАТ С КЛИЕНТОМ ===
# ========================================

async def start_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало чата с клиентом."""
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split("_")[-1])
    context.user_data["chat_user_id"] = user_id

    user = await db.get_user(user_id)
    username = f"@{user['username']}" if user and user.get('username') else ""

    # Получаем историю чата
    history = await db.get_admin_chat_history(user_id, limit=10)

    text = f"💬 <b>ЧАТ С</b> <a href=\"tg://user?id={user_id}\">{escape(user['full_name'] if user else 'Клиент')}</a> {username}\n"
    text += "━━━━━━━━━━━━━━━\n\n"

    if history:
        for msg in history[-5:]:  # Последние 5 сообщений
            direction = "👨‍💼 Ты" if msg['direction'] == 'out' else "👤 Клиент"
            text += f"{direction}: {escape(msg['content'][:100])}\n"
        text += "\n"

    text += "Напишите сообщение клиенту:"

    await query.message.edit_text(
        text,
        reply_markup=kb.admin_chat_kb(user_id),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

    return WAITING_CHAT_MESSAGE


async def process_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка сообщения клиенту."""
    user_id = context.user_data.get("chat_user_id")
    if not user_id:
        return ConversationHandler.END

    admin = update.effective_user
    message_text = update.message.text

    # Сохраняем в историю
    await db.add_admin_chat_message(user_id, admin.id, 'out', 'text', message_text)

    # Отправляем клиенту
    try:
        await context.bot.send_message(
            user_id,
            f"💬 <b>Сообщение от администратора:</b>\n\n{message_text}",
            parse_mode=ParseMode.HTML
        )
        await update.message.reply_text(
            "✅ Сообщение отправлено",
            reply_markup=kb.back_kb(f"adm_chat_{user_id}")
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка отправки: {e}",
            reply_markup=kb.back_kb(f"adm_client_{user_id}")
        )

    return ConversationHandler.END


# ========================================
# === ОБРАБОТКА ВХОДЯЩИХ СООБЩЕНИЙ ОТ КЛИЕНТОВ ===
# ========================================

async def handle_client_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка входящего сообщения от клиента (для чата через бота)."""
    user = update.effective_user
    message = update.message

    # Проверяем, есть ли активный чат с этим клиентом
    # Сохраняем сообщение
    await db.add_admin_chat_message(
        user.id,
        0,  # admin_id = 0 означает сообщение от клиента
        'in',
        'text',
        message.text or message.caption or ''
    )

    # Уведомляем админов, которые следят за этим пользователем
    watchers = await db.is_user_watched(user.id)
    if watchers and LOG_CHANNEL_ID:
        text = (
            f"💬 <b>СООБЩЕНИЕ ОТ КЛИЕНТА</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👤 <a href=\"tg://user?id={user.id}\">{escape(user.full_name)}</a>\n"
            f"📱 @{user.username or 'нет'}\n\n"
            f"💬 {escape(message.text or message.caption or '[медиа]')[:500]}"
        )

        try:
            await context.bot.send_message(
                LOG_CHANNEL_ID,
                text,
                reply_markup=kb.quick_message_kb(user.id),
                parse_mode=ParseMode.HTML
            )
        except:
            pass


# ========================================
# === УВЕДОМЛЕНИЯ О СОБЫТИЯХ ===
# ========================================

async def notify_new_user(context, user):
    """Уведомление о новом пользователе."""
    if not LOG_CHANNEL_ID:
        return

    if not await db.get_notification_setting("new_users"):
        return

    text = (
        f"🆕 <b>НОВЫЙ ПОЛЬЗОВАТЕЛЬ</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 <a href=\"tg://user?id={user.id}\">{escape(user.full_name)}</a>\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📱 Username: @{user.username or 'нет'}\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}"
    )

    try:
        await context.bot.send_message(
            LOG_CHANNEL_ID,
            text,
            reply_markup=kb.quick_user_kb(user.id),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {e}")


async def notify_new_order(context, order_id, user_id):
    """Уведомление о новом заказе."""
    if not LOG_CHANNEL_ID:
        return

    if not await db.get_notification_setting("new_orders"):
        return

    order = await db.get_full_order(order_id)
    if not order:
        return

    username = f"@{order['username']}" if order.get('username') else ""

    text = (
        f"📋 <b>НОВЫЙ ЗАКАЗ #{order_id}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 <a href=\"tg://user?id={user_id}\">{escape(order['full_name'] or 'Клиент')}</a> {username}\n"
        f"📚 Тип: {order['service_type'] or 'Не указан'}\n"
        f"📝 Тема: {escape((order['topic'] or '')[:100])}\n"
        f"💰 Цена: {order['price']}₽\n"
        f"📅 Дедлайн: {order['deadline'] or 'Не указан'}\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}"
    )

    try:
        await context.bot.send_message(
            LOG_CHANNEL_ID,
            text,
            reply_markup=kb.quick_order_kb(order_id),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {e}")


async def notify_promo_used(context, user, code, amount):
    """Уведомление об использовании промокода."""
    if not LOG_CHANNEL_ID:
        return

    if not await db.get_notification_setting("promos"):
        return

    text = (
        f"🎁 <b>ПРОМОКОД АКТИВИРОВАН</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 <a href=\"tg://user?id={user.id}\">{escape(user.full_name)}</a>\n"
        f"📱 @{user.username or 'нет'}\n"
        f"🎟 Код: <code>{code}</code>\n"
        f"💰 Бонус: +{amount}₽\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}"
    )

    try:
        await context.bot.send_message(
            LOG_CHANNEL_ID,
            text,
            reply_markup=kb.quick_user_kb(user.id),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {e}")


# ========================================
# === НАСТРОЙКИ ===
# ========================================

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню настроек."""
    query = update.callback_query
    await query.answer()

    await query.message.edit_text(
        "⚙️ <b>НАСТРОЙКИ</b>\n━━━━━━━━━━━━━━━\n\n"
        "Выберите раздел:",
        reply_markup=kb.settings_kb(),
        parse_mode=ParseMode.HTML
    )


async def backup_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка бэкапа базы данных."""
    query = update.callback_query
    await query.answer("📦 Создаю бэкап...")

    from config import DB_PATH

    try:
        with open(DB_PATH, 'rb') as f:
            await context.bot.send_document(
                query.from_user.id,
                f,
                filename=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                caption="💾 Бэкап базы данных"
            )
        await query.answer("✅ Бэкап отправлен", show_alert=True)
    except Exception as e:
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)


# ========================================
# === ЭКСПОРТ ОБРАБОТЧИКОВ ===
# ========================================

# Алиасы для обратной совместимости с callback_data
admin_panel = show_admin_panel
