import sqlite3
import logging
from config import DB_PATH

# Текущая версия Кодекса Салуна
RULES_VERSION = "1.0"

async def get_connection():
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
