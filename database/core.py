import sqlite3
import logging
from datetime import datetime, timedelta
from config import DB_PATH

# Текущая версия Кодекса Салуна
RULES_VERSION = "1.0"

async def get_connection():
    return sqlite3.connect(DB_PATH)

def get_sync_connection():
    """Синхронное подключение для init_db."""
    return sqlite3.connect(DB_PATH)

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Таблица пользователей с полями для Кодекса
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0,
                orders_count INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                referrer_id INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                -- Поля для Кодекса Салуна
                rules_accepted INTEGER DEFAULT 0,
                rules_version TEXT DEFAULT NULL,
                rules_accepted_at TIMESTAMP DEFAULT NULL,
                welcome_bonus_received INTEGER DEFAULT 0
            )
        """)

        # Таблица заказов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                service_type TEXT,
                topic TEXT,
                deadline TEXT,
                status TEXT DEFAULT 'checking',
                price INTEGER DEFAULT 0,
                files TEXT,
                speech INTEGER DEFAULT 0,
                pres INTEGER DEFAULT 0,
                vip INTEGER DEFAULT 0,
                is_visible INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deadline_type TEXT,
                upsell INTEGER DEFAULT 0
            )
        """)

        # Таблица сообщений чата
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                sender_id INTEGER,
                is_admin INTEGER,
                msg_type TEXT,
                content TEXT,
                file_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица транзакций
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица отзывов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица настроек
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Таблица промокодов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                discount_percent INTEGER DEFAULT 0,
                bonus_amount INTEGER DEFAULT 0,
                max_uses INTEGER DEFAULT 1,
                current_uses INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица использованных промокодов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS used_promos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                promo_code TEXT,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # === ТАБЛИЦЫ ДЛЯ АДМИНКИ ===

        # Логи доступа к админке (попытки входа)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_access_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                full_name TEXT,
                action TEXT,
                success INTEGER DEFAULT 0,
                ip_info TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Заметки админа о клиентах
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                note TEXT,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Блокировки за попытки взлома
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_bans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                attempts INTEGER DEFAULT 0,
                banned_until TIMESTAMP,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Мониторинг пользователей (слежка)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_watchers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                target_user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(admin_id, target_user_id)
            )
        """)

        # Настройки уведомлений
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_settings (
                key TEXT PRIMARY KEY,
                enabled INTEGER DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Рассылки
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT,
                photo_id TEXT,
                filter_type TEXT,
                sent_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER
            )
        """)

        # Чат админа с клиентами (через бота)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                admin_id INTEGER,
                direction TEXT,
                message_type TEXT,
                content TEXT,
                file_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()

        # === МИГРАЦИИ ===
        # Получаем список существующих колонок
        existing_columns = [row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()]

        # Добавляем базовые колонки (если их нет в старой версии БД)
        if 'balance' not in existing_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 0")
        if 'total_spent' not in existing_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN total_spent INTEGER DEFAULT 0")
        if 'orders_count' not in existing_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN orders_count INTEGER DEFAULT 0")

        # Добавляем колонки для Кодекса Салуна (если их нет)
        if 'rules_accepted' not in existing_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN rules_accepted INTEGER DEFAULT 0")
        if 'rules_version' not in existing_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN rules_version TEXT DEFAULT NULL")
        if 'rules_accepted_at' not in existing_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN rules_accepted_at TIMESTAMP DEFAULT NULL")
        if 'welcome_bonus_received' not in existing_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN welcome_bonus_received INTEGER DEFAULT 0")

        conn.commit()

    logging.info("База данных успешно инициализирована.")

# === ПОЛЬЗОВАТЕЛИ ===

async def add_user(user_id, username, full_name, referrer_id=0):
    """Добавить нового пользователя. Возвращает True если новый."""
    conn = await get_connection()
    try:
        cursor = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            return False
        conn.execute(
            "INSERT INTO users (user_id, username, full_name, referrer_id) VALUES (?, ?, ?, ?)",
            (user_id, username, full_name, referrer_id)
        )
        conn.commit()
        return True
    finally:
        conn.close()

async def get_user(user_id):
    """Получить данные пользователя."""
    conn = await get_connection()
    try:
        cursor = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return {
                "user_id": row[0],
                "username": row[1],
                "full_name": row[2],
                "balance": row[3],
                "total_spent": row[4],
                "orders_count": row[5],
                "is_banned": row[6],
                "referrer_id": row[7],
                "joined_at": row[8],
                "rules_accepted": row[9],
                "rules_version": row[10],
                "rules_accepted_at": row[11],
                "welcome_bonus_received": row[12]
            }
        return None
    finally:
        conn.close()

async def check_rules_accepted(user_id):
    """Проверить, принял ли пользователь актуальную версию правил."""
    user = await get_user(user_id)
    if not user:
        return False
    return user['rules_accepted'] == 1 and user['rules_version'] == RULES_VERSION

async def accept_rules(user_id):
    """Записать принятие правил пользователем."""
    conn = await get_connection()
    try:
        conn.execute(
            """UPDATE users
               SET rules_accepted = 1,
                   rules_version = ?,
                   rules_accepted_at = CURRENT_TIMESTAMP
               WHERE user_id = ?""",
            (RULES_VERSION, user_id)
        )
        conn.commit()
    finally:
        conn.close()

async def give_welcome_bonus(user_id, amount=100):
    """Начислить приветственный бонус (только один раз)."""
    conn = await get_connection()
    try:
        # Проверяем, получал ли уже бонус
        cursor = conn.execute(
            "SELECT welcome_bonus_received FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        if row and row[0] == 1:
            return False  # Уже получал

        # Начисляем бонус
        conn.execute(
            "UPDATE users SET balance = balance + ?, welcome_bonus_received = 1 WHERE user_id = ?",
            (amount, user_id)
        )

        # Записываем транзакцию
        conn.execute(
            "INSERT INTO transactions (user_id, amount, reason) VALUES (?, ?, ?)",
            (user_id, amount, "Приветственный бонус за вступление в Салун")
        )
        conn.commit()
        return True
    finally:
        conn.close()

async def update_user_field(user_id, field, value):
    """Обновить поле пользователя."""
    conn = await get_connection()
    try:
        conn.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
        conn.commit()
    finally:
        conn.close()

async def add_balance(user_id, amount, reason=""):
    """Добавить баланс пользователю."""
    conn = await get_connection()
    try:
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        conn.execute(
            "INSERT INTO transactions (user_id, amount, reason) VALUES (?, ?, ?)",
            (user_id, amount, reason)
        )
        conn.commit()
    finally:
        conn.close()

async def get_all_users():
    """Получить всех пользователей."""
    conn = await get_connection()
    try:
        cursor = conn.execute("SELECT user_id, full_name, username, balance, is_banned, referrer_id FROM users")
        users = []
        for row in cursor.fetchall():
            users.append({
                "user_id": row[0],
                "full_name": row[1],
                "username": row[2],
                "balance": row[3],
                "is_banned": row[4],
                "referrer_id": row[5]
            })
        return users
    finally:
        conn.close()

# === ЗАКАЗЫ ===

async def create_order(data):
    """Создать новый заказ."""
    conn = await get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO orders (user_id, service_type, topic, deadline_type, price, files, status, deadline)
               VALUES (?, ?, ?, ?, ?, ?, 'checking', ?)""",
            (data['uid'], data['type'], data['topic'], data['deadline'], data['price'], "", data['deadline'])
        )
        conn.commit()
        oid = cursor.lastrowid
        conn.execute("UPDATE users SET orders_count = orders_count + 1 WHERE user_id = ?", (data['uid'],))
        conn.commit()
        return oid
    finally:
        conn.close()

async def get_order(order_id):
    """Получить заказ по ID."""
    conn = await get_connection()
    try:
        cursor = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "user_id": row[1],
                "service_type": row[2],
                "topic": row[3],
                "deadline": row[4],
                "status": row[5],
                "price": row[6],
                "files": row[7],
                "created_at": row[12],
                "deadline_type": row[13]
            }
        return None
    finally:
        conn.close()

async def get_user_orders(user_id):
    """Получить заказы пользователя."""
    conn = await get_connection()
    try:
        cursor = conn.execute(
            "SELECT * FROM orders WHERE user_id = ? AND is_visible = 1 ORDER BY id DESC",
            (user_id,)
        )
        orders = []
        for row in cursor.fetchall():
            orders.append({
                "id": row[0],
                "status": row[5],
                "price": row[6],
                "service_type": row[2],
                "topic": row[3],
                "deadline": row[4]
            })
        return orders
    finally:
        conn.close()

async def get_all_orders(limit=100):
    """Получить все активные заказы."""
    conn = await get_connection()
    try:
        cursor = conn.execute(
            "SELECT * FROM orders WHERE status != 'done' ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        orders = []
        for row in cursor.fetchall():
            orders.append({
                "id": row[0],
                "user_id": row[1],
                "status": row[5],
                "price": row[6],
                "service_type": row[2],
                "topic": row[3]
            })
        return orders
    finally:
        conn.close()

async def update_order_status(order_id, new_status):
    """Обновить статус заказа."""
    conn = await get_connection()
    try:
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
        conn.commit()
    finally:
        conn.close()

async def update_order_visibility(order_id, is_visible):
    """Скрыть/показать заказ."""
    conn = await get_connection()
    try:
        conn.execute("UPDATE orders SET is_visible = ? WHERE id = ?", (1 if is_visible else 0, order_id))
        conn.commit()
    finally:
        conn.close()

# === ЧАТ ===

async def add_chat_message(order_id, sender_id, is_admin, msg_type, content, file_id=None):
    """Добавить сообщение в чат."""
    conn = await get_connection()
    try:
        conn.execute(
            """INSERT INTO messages (order_id, sender_id, is_admin, msg_type, content, file_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (order_id, sender_id, 1 if is_admin else 0, msg_type, content, file_id)
        )
        conn.commit()
    finally:
        conn.close()

async def get_chat_history(order_id):
    """Получить историю чата по заказу."""
    conn = await get_connection()
    try:
        cursor = conn.execute(
            """SELECT sender_id, is_admin, msg_type, content, file_id, created_at
               FROM messages WHERE order_id = ? ORDER BY id ASC""",
            (order_id,)
        )
        res = []
        for row in cursor.fetchall():
            res.append({
                "sender_id": row[0],
                "is_admin": row[1],
                "message_type": row[2],
                "content": row[3],
                "file_id": row[4],
                "created_at": row[5]
            })
        return res
    finally:
        conn.close()

# === ОТЗЫВЫ ===

async def add_review(user_id, text):
    """Добавить отзыв."""
    conn = await get_connection()
    try:
        conn.execute("INSERT INTO reviews (user_id, text) VALUES (?, ?)", (user_id, text))
        conn.commit()
    finally:
        conn.close()

# === ТРАНЗАКЦИИ ===

async def get_transactions(user_id):
    """Получить транзакции пользователя."""
    conn = await get_connection()
    try:
        cursor = conn.execute(
            "SELECT amount, reason, created_at FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 10",
            (user_id,)
        )
        res = []
        for row in cursor.fetchall():
            res.append({"amount": row[0], "reason": row[1], "date": row[2]})
        return res
    finally:
        conn.close()

# === ПРОМОКОДЫ ===

async def check_promo_code(code, user_id):
    """Проверить промокод. Возвращает данные промокода или None."""
    conn = await get_connection()
    try:
        # Проверяем, не использовал ли уже
        cursor = conn.execute(
            "SELECT id FROM used_promos WHERE user_id = ? AND promo_code = ?",
            (user_id, code.upper())
        )
        if cursor.fetchone():
            return {"error": "already_used"}

        # Проверяем промокод
        cursor = conn.execute(
            """SELECT code, discount_percent, bonus_amount, max_uses, current_uses, is_active
               FROM promo_codes WHERE code = ? AND is_active = 1""",
            (code.upper(),)
        )
        row = cursor.fetchone()
        if not row:
            return None

        if row[4] >= row[3]:  # current_uses >= max_uses
            return {"error": "max_uses"}

        return {
            "code": row[0],
            "discount_percent": row[1],
            "bonus_amount": row[2]
        }
    finally:
        conn.close()

async def use_promo_code(code, user_id):
    """Использовать промокод."""
    conn = await get_connection()
    try:
        conn.execute(
            "UPDATE promo_codes SET current_uses = current_uses + 1 WHERE code = ?",
            (code.upper(),)
        )
        conn.execute(
            "INSERT INTO used_promos (user_id, promo_code) VALUES (?, ?)",
            (user_id, code.upper())
        )
        conn.commit()
    finally:
        conn.close()

async def create_promo_code(code, discount_percent=0, bonus_amount=0, max_uses=1):
    """Создать промокод."""
    conn = await get_connection()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO promo_codes (code, discount_percent, bonus_amount, max_uses, is_active)
               VALUES (?, ?, ?, ?, 1)""",
            (code.upper(), discount_percent, bonus_amount, max_uses)
        )
        conn.commit()
    finally:
        conn.close()

# === НАСТРОЙКИ ===

async def get_setting(key):
    """Получить настройку."""
    conn = await get_connection()
    try:
        cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()

async def set_setting(key, value):
    """Установить настройку."""
    conn = await get_connection()
    try:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()
    finally:
        conn.close()

# === СТАТИСТИКА ===

async def get_stats():
    """Получить статистику."""
    conn = await get_connection()
    try:
        u_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        o_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        money = conn.execute("SELECT SUM(price) FROM orders WHERE status != 'cancel'").fetchone()[0] or 0
        return u_count, o_count, money
    finally:
        conn.close()


# === ЛОГИРОВАНИЕ И ПОВЕДЕНИЕ (для utils.py) ===

async def get_user_behavior_snapshot(user_id):
    """Получить снапшот поведения пользователя для аналитики."""
    user = await get_user(user_id)
    if not user:
        return {}
    return {
        "total_spent": user.get("total_spent", 0),
        "orders_count": user.get("orders_count", 0),
        "price_clicks": 0,  # Можно расширить
        "total_actions": 0,
        "night_actions": 0
    }


async def add_action_log(user_id, action, event_type=None, meta=None):
    """Добавить лог действия (заглушка для совместимости)."""
    # Можно расширить для детальной аналитики
    pass


# ========================================
# === ФУНКЦИИ ДЛЯ СУПЕР-АДМИНКИ ===
# ========================================

# --- БЕЗОПАСНОСТЬ ---

async def log_admin_access(user_id, username, full_name, action, success=False, ip_info=None):
    """Логирование попытки доступа к админке."""
    conn = await get_connection()
    try:
        conn.execute(
            """INSERT INTO admin_access_log (user_id, username, full_name, action, success, ip_info)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, username, full_name, action, 1 if success else 0, ip_info)
        )
        conn.commit()
    finally:
        conn.close()


async def get_admin_ban(user_id):
    """Проверить, заблокирован ли пользователь за попытки взлома."""
    conn = await get_connection()
    try:
        cursor = conn.execute(
            "SELECT attempts, banned_until, reason FROM admin_bans WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "attempts": row[0],
                "banned_until": row[1],
                "reason": row[2]
            }
        return None
    finally:
        conn.close()


async def add_admin_attempt(user_id, max_attempts=3, ban_time=3600):
    """Добавить неудачную попытку входа. Возвращает True если забанен."""
    conn = await get_connection()
    try:
        cursor = conn.execute(
            "SELECT attempts FROM admin_bans WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()

        if row:
            new_attempts = row[0] + 1
            if new_attempts >= max_attempts:
                banned_until = datetime.now() + timedelta(seconds=ban_time)
                conn.execute(
                    """UPDATE admin_bans
                       SET attempts = ?, banned_until = ?, reason = 'Превышено количество попыток входа'
                       WHERE user_id = ?""",
                    (new_attempts, banned_until.isoformat(), user_id)
                )
                conn.commit()
                return True
            else:
                conn.execute(
                    "UPDATE admin_bans SET attempts = ? WHERE user_id = ?",
                    (new_attempts, user_id)
                )
                conn.commit()
                return False
        else:
            conn.execute(
                "INSERT INTO admin_bans (user_id, attempts) VALUES (?, 1)",
                (user_id,)
            )
            conn.commit()
            return False
    finally:
        conn.close()


async def reset_admin_attempts(user_id):
    """Сбросить счетчик неудачных попыток."""
    conn = await get_connection()
    try:
        conn.execute("DELETE FROM admin_bans WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


# --- ЗАМЕТКИ О КЛИЕНТАХ ---

async def get_admin_note(user_id):
    """Получить заметку о клиенте."""
    conn = await get_connection()
    try:
        cursor = conn.execute(
            "SELECT note, created_at, updated_at FROM admin_notes WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        row = cursor.fetchone()
        return {"note": row[0], "created_at": row[1], "updated_at": row[2]} if row else None
    finally:
        conn.close()


async def set_admin_note(user_id, note, admin_id):
    """Установить заметку о клиенте."""
    conn = await get_connection()
    try:
        # Проверяем, есть ли уже заметка
        cursor = conn.execute("SELECT id FROM admin_notes WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            conn.execute(
                "UPDATE admin_notes SET note = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (note, user_id)
            )
        else:
            conn.execute(
                "INSERT INTO admin_notes (user_id, note, created_by) VALUES (?, ?, ?)",
                (user_id, note, admin_id)
            )
        conn.commit()
    finally:
        conn.close()


# --- МОНИТОРИНГ ПОЛЬЗОВАТЕЛЕЙ ---

async def add_watcher(admin_id, target_user_id):
    """Добавить пользователя в мониторинг."""
    conn = await get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO admin_watchers (admin_id, target_user_id) VALUES (?, ?)",
            (admin_id, target_user_id)
        )
        conn.commit()
    finally:
        conn.close()


async def remove_watcher(admin_id, target_user_id):
    """Убрать пользователя из мониторинга."""
    conn = await get_connection()
    try:
        conn.execute(
            "DELETE FROM admin_watchers WHERE admin_id = ? AND target_user_id = ?",
            (admin_id, target_user_id)
        )
        conn.commit()
    finally:
        conn.close()


async def get_watched_users(admin_id):
    """Получить список отслеживаемых пользователей."""
    conn = await get_connection()
    try:
        cursor = conn.execute(
            "SELECT target_user_id FROM admin_watchers WHERE admin_id = ?",
            (admin_id,)
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


async def is_user_watched(user_id):
    """Проверить, отслеживается ли пользователь."""
    conn = await get_connection()
    try:
        cursor = conn.execute(
            "SELECT admin_id FROM admin_watchers WHERE target_user_id = ?",
            (user_id,)
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


# --- НАСТРОЙКИ УВЕДОМЛЕНИЙ ---

async def get_notification_setting(key):
    """Получить настройку уведомления."""
    conn = await get_connection()
    try:
        cursor = conn.execute("SELECT enabled FROM notification_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] == 1 if row else True  # По умолчанию включено
    finally:
        conn.close()


async def set_notification_setting(key, enabled):
    """Установить настройку уведомления."""
    conn = await get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO notification_settings (key, enabled, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (key, 1 if enabled else 0)
        )
        conn.commit()
    finally:
        conn.close()


async def get_all_notification_settings():
    """Получить все настройки уведомлений."""
    conn = await get_connection()
    try:
        cursor = conn.execute("SELECT key, enabled FROM notification_settings")
        return {row[0]: row[1] == 1 for row in cursor.fetchall()}
    finally:
        conn.close()


# --- РАССЫЛКИ ---

async def create_broadcast(text, photo_id, filter_type, admin_id):
    """Создать запись о рассылке."""
    conn = await get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO broadcasts (text, photo_id, filter_type, created_by)
               VALUES (?, ?, ?, ?)""",
            (text, photo_id, filter_type, admin_id)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


async def update_broadcast_count(broadcast_id, count):
    """Обновить количество отправленных сообщений."""
    conn = await get_connection()
    try:
        conn.execute(
            "UPDATE broadcasts SET sent_count = ? WHERE id = ?",
            (count, broadcast_id)
        )
        conn.commit()
    finally:
        conn.close()


# --- ЧАТ АДМИНА С КЛИЕНТАМИ ---

async def add_admin_chat_message(user_id, admin_id, direction, message_type, content, file_id=None):
    """Добавить сообщение в чат админа с клиентом."""
    conn = await get_connection()
    try:
        conn.execute(
            """INSERT INTO admin_chats (user_id, admin_id, direction, message_type, content, file_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, admin_id, direction, message_type, content, file_id)
        )
        conn.commit()
    finally:
        conn.close()


async def get_admin_chat_history(user_id, limit=50):
    """Получить историю чата с клиентом."""
    conn = await get_connection()
    try:
        cursor = conn.execute(
            """SELECT direction, message_type, content, file_id, created_at
               FROM admin_chats WHERE user_id = ? ORDER BY id DESC LIMIT ?""",
            (user_id, limit)
        )
        messages = []
        for row in cursor.fetchall():
            messages.append({
                "direction": row[0],
                "message_type": row[1],
                "content": row[2],
                "file_id": row[3],
                "created_at": row[4]
            })
        return list(reversed(messages))
    finally:
        conn.close()


# --- РАСШИРЕННАЯ СТАТИСТИКА ---

async def get_extended_stats():
    """Расширенная статистика для дашборда."""
    conn = await get_connection()
    try:
        stats = {}

        # Пользователи
        stats['total_users'] = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        stats['today_users'] = conn.execute(
            "SELECT COUNT(*) FROM users WHERE DATE(joined_at) = DATE('now')"
        ).fetchone()[0]
        stats['week_users'] = conn.execute(
            "SELECT COUNT(*) FROM users WHERE joined_at >= DATE('now', '-7 days')"
        ).fetchone()[0]

        # Заказы
        stats['total_orders'] = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        stats['checking_orders'] = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status = 'checking'"
        ).fetchone()[0]
        stats['work_orders'] = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status = 'work'"
        ).fetchone()[0]
        stats['done_orders'] = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status = 'done'"
        ).fetchone()[0]

        # Финансы
        stats['total_revenue'] = conn.execute(
            "SELECT COALESCE(SUM(price), 0) FROM orders WHERE status != 'cancel'"
        ).fetchone()[0]
        stats['month_revenue'] = conn.execute(
            "SELECT COALESCE(SUM(price), 0) FROM orders WHERE status != 'cancel' AND created_at >= DATE('now', '-30 days')"
        ).fetchone()[0]
        stats['week_revenue'] = conn.execute(
            "SELECT COALESCE(SUM(price), 0) FROM orders WHERE status != 'cancel' AND created_at >= DATE('now', '-7 days')"
        ).fetchone()[0]
        stats['today_revenue'] = conn.execute(
            "SELECT COALESCE(SUM(price), 0) FROM orders WHERE status != 'cancel' AND DATE(created_at) = DATE('now')"
        ).fetchone()[0]

        # Средний чек
        avg = conn.execute(
            "SELECT AVG(price) FROM orders WHERE status != 'cancel' AND price > 0"
        ).fetchone()[0]
        stats['avg_order'] = round(avg, 0) if avg else 0

        # Конверсия
        users_with_orders = conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM orders"
        ).fetchone()[0]
        stats['conversion'] = round(users_with_orders / stats['total_users'] * 100, 1) if stats['total_users'] > 0 else 0

        # Бонусы
        stats['total_bonuses'] = conn.execute(
            "SELECT COALESCE(SUM(balance), 0) FROM users"
        ).fetchone()[0]

        return stats
    finally:
        conn.close()


async def get_users_paginated(page=1, per_page=10, filter_type=None, search=None):
    """Получить пользователей с пагинацией и фильтрами."""
    conn = await get_connection()
    try:
        offset = (page - 1) * per_page

        where_clauses = []
        params = []

        if filter_type == "with_orders":
            where_clauses.append("orders_count > 0")
        elif filter_type == "without_orders":
            where_clauses.append("orders_count = 0")
        elif filter_type == "banned":
            where_clauses.append("is_banned = 1")

        if search:
            where_clauses.append("(username LIKE ? OR full_name LIKE ? OR CAST(user_id AS TEXT) LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Получаем общее количество
        count_sql = f"SELECT COUNT(*) FROM users{where_sql}"
        total = conn.execute(count_sql, params).fetchone()[0]

        # Получаем пользователей
        sql = f"""
            SELECT user_id, username, full_name, balance, total_spent, orders_count,
                   is_banned, referrer_id, joined_at, rules_accepted
            FROM users{where_sql}
            ORDER BY joined_at DESC
            LIMIT ? OFFSET ?
        """
        cursor = conn.execute(sql, params + [per_page, offset])

        users = []
        for row in cursor.fetchall():
            users.append({
                "user_id": row[0],
                "username": row[1],
                "full_name": row[2],
                "balance": row[3],
                "total_spent": row[4],
                "orders_count": row[5],
                "is_banned": row[6],
                "referrer_id": row[7],
                "joined_at": row[8],
                "rules_accepted": row[9]
            })

        return {
            "users": users,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page
        }
    finally:
        conn.close()


async def get_orders_paginated(page=1, per_page=10, status_filter=None, user_id=None):
    """Получить заказы с пагинацией и фильтрами."""
    conn = await get_connection()
    try:
        offset = (page - 1) * per_page

        where_clauses = []
        params = []

        if status_filter and status_filter != "all":
            where_clauses.append("o.status = ?")
            params.append(status_filter)

        if user_id:
            where_clauses.append("o.user_id = ?")
            params.append(user_id)

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Получаем общее количество
        count_sql = f"SELECT COUNT(*) FROM orders o{where_sql}"
        total = conn.execute(count_sql, params).fetchone()[0]

        # Получаем заказы с данными пользователей
        sql = f"""
            SELECT o.id, o.user_id, o.service_type, o.topic, o.deadline, o.status,
                   o.price, o.created_at, u.username, u.full_name
            FROM orders o
            LEFT JOIN users u ON o.user_id = u.user_id
            {where_sql}
            ORDER BY o.id DESC
            LIMIT ? OFFSET ?
        """
        cursor = conn.execute(sql, params + [per_page, offset])

        orders = []
        for row in cursor.fetchall():
            orders.append({
                "id": row[0],
                "user_id": row[1],
                "service_type": row[2],
                "topic": row[3],
                "deadline": row[4],
                "status": row[5],
                "price": row[6],
                "created_at": row[7],
                "username": row[8],
                "full_name": row[9]
            })

        return {
            "orders": orders,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page
        }
    finally:
        conn.close()


async def get_full_order(order_id):
    """Получить полную информацию о заказе."""
    conn = await get_connection()
    try:
        cursor = conn.execute(
            """SELECT o.*, u.username, u.full_name, u.balance
               FROM orders o
               LEFT JOIN users u ON o.user_id = u.user_id
               WHERE o.id = ?""",
            (order_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "user_id": row[1],
                "service_type": row[2],
                "topic": row[3],
                "deadline": row[4],
                "status": row[5],
                "price": row[6],
                "files": row[7],
                "speech": row[8],
                "pres": row[9],
                "vip": row[10],
                "is_visible": row[11],
                "created_at": row[12],
                "deadline_type": row[13],
                "upsell": row[14],
                "username": row[15],
                "full_name": row[16],
                "user_balance": row[17]
            }
        return None
    finally:
        conn.close()


async def update_order_price(order_id, new_price):
    """Обновить цену заказа."""
    conn = await get_connection()
    try:
        conn.execute("UPDATE orders SET price = ? WHERE id = ?", (new_price, order_id))
        conn.commit()
    finally:
        conn.close()


async def ban_user(user_id, reason=""):
    """Забанить пользователя."""
    conn = await get_connection()
    try:
        conn.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


async def unban_user(user_id):
    """Разбанить пользователя."""
    conn = await get_connection()
    try:
        conn.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


async def get_revenue_by_service():
    """Получить выручку по типам услуг."""
    conn = await get_connection()
    try:
        cursor = conn.execute(
            """SELECT service_type, COUNT(*) as cnt, COALESCE(SUM(price), 0) as total
               FROM orders WHERE status != 'cancel'
               GROUP BY service_type
               ORDER BY total DESC"""
        )
        result = []
        for row in cursor.fetchall():
            result.append({
                "service_type": row[0],
                "count": row[1],
                "revenue": row[2]
            })
        return result
    finally:
        conn.close()


async def get_referral_stats():
    """Статистика по рефералам."""
    conn = await get_connection()
    try:
        cursor = conn.execute(
            """SELECT referrer_id, COUNT(*) as cnt
               FROM users WHERE referrer_id > 0
               GROUP BY referrer_id
               ORDER BY cnt DESC
               LIMIT 10"""
        )
        result = []
        for row in cursor.fetchall():
            referrer = await get_user(row[0])
            result.append({
                "user_id": row[0],
                "username": referrer.get("username") if referrer else None,
                "full_name": referrer.get("full_name") if referrer else "Неизвестно",
                "referrals_count": row[1]
            })
        return result
    finally:
        conn.close()


async def get_promo_stats():
    """Статистика по промокодам."""
    conn = await get_connection()
    try:
        cursor = conn.execute(
            """SELECT code, discount_percent, bonus_amount, max_uses, current_uses, is_active
               FROM promo_codes
               ORDER BY current_uses DESC"""
        )
        result = []
        for row in cursor.fetchall():
            result.append({
                "code": row[0],
                "discount_percent": row[1],
                "bonus_amount": row[2],
                "max_uses": row[3],
                "current_uses": row[4],
                "is_active": row[5]
            })
        return result
    finally:
        conn.close()


async def deactivate_promo_code(code):
    """Деактивировать промокод."""
    conn = await get_connection()
    try:
        conn.execute("UPDATE promo_codes SET is_active = 0 WHERE code = ?", (code.upper(),))
        conn.commit()
    finally:
        conn.close()


async def activate_promo_code(code):
    """Активировать промокод."""
    conn = await get_connection()
    try:
        conn.execute("UPDATE promo_codes SET is_active = 1 WHERE code = ?", (code.upper(),))
        conn.commit()
    finally:
        conn.close()


async def get_users_for_broadcast(filter_type="all"):
    """Получить список пользователей для рассылки."""
    conn = await get_connection()
    try:
        if filter_type == "with_orders":
            cursor = conn.execute("SELECT user_id FROM users WHERE orders_count > 0 AND is_banned = 0")
        elif filter_type == "without_orders":
            cursor = conn.execute("SELECT user_id FROM users WHERE orders_count = 0 AND is_banned = 0")
        elif filter_type == "vip":
            cursor = conn.execute("SELECT user_id FROM users WHERE total_spent >= 10000 AND is_banned = 0")
        else:
            cursor = conn.execute("SELECT user_id FROM users WHERE is_banned = 0")

        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()
