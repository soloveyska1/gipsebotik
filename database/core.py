"""
🗄️ БАЗА ДАННЫХ - ЯДРО СИСТЕМЫ
Полный контроль над всеми данными
"""
import sqlite3
import logging
from datetime import datetime
from config import DB_PATH

logger = logging.getLogger(__name__)

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализация БД с расширенными таблицами для аналитики"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # === ПОЛЬЗОВАТЕЛИ ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                phone TEXT,
                balance INTEGER DEFAULT 0,
                bonus_balance INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0,
                orders_count INTEGER DEFAULT 0,
                completed_orders INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                ban_reason TEXT,
                referrer_id INTEGER DEFAULT 0,
                referral_earnings INTEGER DEFAULT 0,
                vip_level INTEGER DEFAULT 0,
                discount_percent INTEGER DEFAULT 0,
                tags TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                source TEXT DEFAULT 'organic',
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_action TEXT,
                session_count INTEGER DEFAULT 1
            )
        """)

        # === ЗАКАЗЫ ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                service_type TEXT,
                topic TEXT,
                description TEXT,
                deadline TEXT,
                deadline_type TEXT,
                status TEXT DEFAULT 'new',
                substatus TEXT DEFAULT '',
                price INTEGER DEFAULT 0,
                paid_amount INTEGER DEFAULT 0,
                payment_status TEXT DEFAULT 'not_paid',
                files TEXT DEFAULT '',
                result_files TEXT DEFAULT '',
                assigned_worker TEXT,
                manager_id INTEGER,
                priority INTEGER DEFAULT 0,
                is_urgent INTEGER DEFAULT 0,
                is_visible INTEGER DEFAULT 1,
                client_rating INTEGER,
                client_feedback TEXT,
                internal_notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                last_client_msg TIMESTAMP,
                last_admin_msg TIMESTAMP,
                upsell INTEGER DEFAULT 0,
                speech INTEGER DEFAULT 0,
                pres INTEGER DEFAULT 0,
                vip INTEGER DEFAULT 0
            )
        """)

        # === ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЕЙ (ДЛЯ СЛЕЖКИ) ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action_type TEXT,
                action_data TEXT,
                screen TEXT,
                button_clicked TEXT,
                message_text TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # === ВОРОНКА ПРОДАЖ ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS funnel_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                stage TEXT,
                previous_stage TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                time_in_stage INTEGER DEFAULT 0
            )
        """)

        # === СООБЩЕНИЯ ЧАТА ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                sender_id INTEGER,
                is_admin INTEGER DEFAULT 0,
                msg_type TEXT,
                content TEXT,
                file_id TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # === ТРАНЗАКЦИИ ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                order_id INTEGER,
                amount INTEGER,
                type TEXT,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # === ОТЗЫВЫ ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                order_id INTEGER,
                rating INTEGER,
                text TEXT,
                is_published INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # === НАСТРОЙКИ ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # === АЛЕРТЫ АДМИНУ ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT,
                user_id INTEGER,
                order_id INTEGER,
                message TEXT,
                priority INTEGER DEFAULT 0,
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # === БРОШЕННЫЕ КОРЗИНЫ ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS abandoned_carts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                stage TEXT,
                cart_data TEXT,
                reminder_sent INTEGER DEFAULT 0,
                recovered INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
    logger.info("✅ База данных инициализирована")


# ==================== ПОЛЬЗОВАТЕЛИ ====================

async def add_user(user_id, username, full_name, referrer_id=0, source='organic'):
    with get_connection() as conn:
        cursor = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            conn.execute("""
                UPDATE users SET last_seen = ?, session_count = session_count + 1
                WHERE user_id = ?
            """, (datetime.now(), user_id))
            conn.commit()
            return False
        conn.execute("""
            INSERT INTO users (user_id, username, full_name, referrer_id, source)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, username, full_name, referrer_id, source))
        conn.commit()
        await create_alert('new_user', user_id, None, f"🆕 Новый: {full_name}")
        return True

async def get_user(user_id):
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

async def get_all_users(limit=100, offset=0, filter_type=None):
    with get_connection() as conn:
        query = "SELECT * FROM users"
        params = []

        if filter_type == 'active':
            query += " WHERE last_seen > datetime('now', '-7 days')"
        elif filter_type == 'with_orders':
            query += " WHERE orders_count > 0"
        elif filter_type == 'no_orders':
            query += " WHERE orders_count = 0"
        elif filter_type == 'vip':
            query += " WHERE vip_level > 0"
        elif filter_type == 'banned':
            query += " WHERE is_banned = 1"

        query += " ORDER BY last_seen DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

async def update_user_field(user_id, field, value):
    with get_connection() as conn:
        conn.execute(f"UPDATE users SET {field} = ?, last_seen = ? WHERE user_id = ?",
                    (value, datetime.now(), user_id))
        conn.commit()

async def update_user_activity(user_id, action):
    with get_connection() as conn:
        conn.execute("""
            UPDATE users SET last_seen = ?, last_action = ? WHERE user_id = ?
        """, (datetime.now(), action, user_id))
        conn.commit()

async def ban_user(user_id, reason=""):
    with get_connection() as conn:
        conn.execute("UPDATE users SET is_banned = 1, ban_reason = ? WHERE user_id = ?",
                    (reason, user_id))
        conn.commit()

async def unban_user(user_id):
    with get_connection() as conn:
        conn.execute("UPDATE users SET is_banned = 0, ban_reason = '' WHERE user_id = ?", (user_id,))
        conn.commit()

async def add_user_tag(user_id, tag):
    user = await get_user(user_id)
    if user:
        tags = user.get('tags', '') or ''
        if tag not in tags:
            tags = f"{tags},{tag}" if tags else tag
            await update_user_field(user_id, 'tags', tags)

async def add_user_note(user_id, note):
    user = await get_user(user_id)
    if user:
        notes = user.get('notes', '') or ''
        timestamp = datetime.now().strftime('%d.%m %H:%M')
        new_note = f"[{timestamp}] {note}"
        notes = f"{notes}\n{new_note}" if notes else new_note
        await update_user_field(user_id, 'notes', notes)

async def search_users(query):
    """Поиск пользователей по имени/username/ID"""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM users
            WHERE full_name LIKE ? OR username LIKE ? OR CAST(user_id AS TEXT) LIKE ?
            ORDER BY last_seen DESC LIMIT 20
        """, (f'%{query}%', f'%{query}%', f'%{query}%'))
        return [dict(row) for row in cursor.fetchall()]


# ==================== ЗАКАЗЫ ====================

async def create_order(data):
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO orders (user_id, service_type, topic, description, deadline, deadline_type, price, files, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new')
        """, (data['uid'], data['type'], data['topic'], data.get('desc', ''),
              data['deadline'], data.get('deadline_type', ''), data['price'], data.get('files', '')))
        conn.commit()
        order_id = cursor.lastrowid
        conn.execute("UPDATE users SET orders_count = orders_count + 1 WHERE user_id = ?", (data['uid'],))
        conn.commit()
        await create_alert('new_order', data['uid'], order_id, f"🔥 Новый заказ #{order_id}: {data['type']}", priority=2)
        return order_id

async def get_order(order_id):
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

async def get_user_orders(user_id):
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM orders WHERE user_id = ? AND is_visible = 1 ORDER BY id DESC
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]

async def get_all_orders(status=None, limit=50):
    with get_connection() as conn:
        if status:
            cursor = conn.execute("""
                SELECT o.*, u.full_name, u.username, u.phone
                FROM orders o LEFT JOIN users u ON o.user_id = u.user_id
                WHERE o.status = ?
                ORDER BY o.priority DESC, o.created_at DESC LIMIT ?
            """, (status, limit))
        else:
            cursor = conn.execute("""
                SELECT o.*, u.full_name, u.username, u.phone
                FROM orders o LEFT JOIN users u ON o.user_id = u.user_id
                WHERE o.status NOT IN ('done', 'cancelled')
                ORDER BY o.priority DESC, o.created_at DESC LIMIT ?
            """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

async def update_order_status(order_id, new_status, substatus=''):
    with get_connection() as conn:
        conn.execute("""
            UPDATE orders SET status = ?, substatus = ?, updated_at = ? WHERE id = ?
        """, (new_status, substatus, datetime.now(), order_id))
        conn.commit()
        if new_status == 'done':
            conn.execute("UPDATE orders SET completed_at = ? WHERE id = ?", (datetime.now(), order_id))
            order = await get_order(order_id)
            if order:
                conn.execute("UPDATE users SET completed_orders = completed_orders + 1 WHERE user_id = ?", (order['user_id'],))
            conn.commit()

async def update_order_field(order_id, field, value):
    with get_connection() as conn:
        conn.execute(f"UPDATE orders SET {field} = ?, updated_at = ? WHERE id = ?",
                    (value, datetime.now(), order_id))
        conn.commit()

async def update_order_visibility(order_id, is_visible):
    with get_connection() as conn:
        conn.execute("UPDATE orders SET is_visible = ? WHERE id = ?", (1 if is_visible else 0, order_id))
        conn.commit()


# ==================== ДЕЙСТВИЯ / АНАЛИТИКА ====================

async def log_action(user_id, action_type, action_data='', screen='', button='', message=''):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO user_actions (user_id, action_type, action_data, screen, button_clicked, message_text)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, action_type, action_data, screen, button, message[:500] if message else ''))
        conn.commit()

async def add_action_log(user_id, action, event_type='action', meta=''):
    await log_action(user_id, event_type, meta, '', '', action)

async def get_user_actions(user_id, limit=50):
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM user_actions WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?
        """, (user_id, limit))
        return [dict(row) for row in cursor.fetchall()]

async def get_recent_actions(limit=100):
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT a.*, u.full_name, u.username
            FROM user_actions a LEFT JOIN users u ON a.user_id = u.user_id
            ORDER BY a.timestamp DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

async def get_user_behavior_snapshot(user_id):
    user = await get_user(user_id)
    if not user:
        return {}
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT COUNT(*) as total_actions,
                   SUM(CASE WHEN time(timestamp) BETWEEN '00:00' AND '06:00' THEN 1 ELSE 0 END) as night_actions,
                   SUM(CASE WHEN button_clicked LIKE '%price%' THEN 1 ELSE 0 END) as price_clicks
            FROM user_actions WHERE user_id = ?
        """, (user_id,))
        stats = dict(cursor.fetchone())
        stats.update(user)
        return stats


# ==================== ВОРОНКА ====================

async def track_funnel(user_id, stage):
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT stage, timestamp FROM funnel_events WHERE user_id = ? ORDER BY id DESC LIMIT 1
        """, (user_id,))
        prev = cursor.fetchone()
        prev_stage = prev['stage'] if prev else None
        time_in_prev = 0
        if prev:
            try:
                time_in_prev = int((datetime.now() - datetime.fromisoformat(prev['timestamp'])).total_seconds())
            except:
                pass
        conn.execute("""
            INSERT INTO funnel_events (user_id, stage, previous_stage, time_in_stage)
            VALUES (?, ?, ?, ?)
        """, (user_id, stage, prev_stage, time_in_prev))
        conn.commit()


# ==================== АЛЕРТЫ ====================

async def create_alert(alert_type, user_id, order_id, message, priority=0):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO admin_alerts (alert_type, user_id, order_id, message, priority)
            VALUES (?, ?, ?, ?, ?)
        """, (alert_type, user_id, order_id, message, priority))
        conn.commit()

async def get_unread_alerts(limit=20):
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT a.*, u.full_name, u.username
            FROM admin_alerts a LEFT JOIN users u ON a.user_id = u.user_id
            WHERE a.is_read = 0 ORDER BY a.priority DESC, a.created_at DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

async def mark_alert_read(alert_id):
    with get_connection() as conn:
        conn.execute("UPDATE admin_alerts SET is_read = 1 WHERE id = ?", (alert_id,))
        conn.commit()

async def mark_all_alerts_read():
    with get_connection() as conn:
        conn.execute("UPDATE admin_alerts SET is_read = 1")
        conn.commit()


# ==================== ЧАТ ====================

async def add_chat_message(order_id, sender_id, is_admin, msg_type, content, file_id=None):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO messages (order_id, sender_id, is_admin, msg_type, content, file_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (order_id, sender_id, 1 if is_admin else 0, msg_type, content, file_id))
        conn.commit()
        field = 'last_admin_msg' if is_admin else 'last_client_msg'
        conn.execute(f"UPDATE orders SET {field} = ? WHERE id = ?", (datetime.now(), order_id))
        conn.commit()

async def get_chat_history(order_id):
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM messages WHERE order_id = ? ORDER BY id ASC", (order_id,))
        return [dict(row) for row in cursor.fetchall()]

async def get_unread_messages_count(order_id, is_admin=True):
    with get_connection() as conn:
        if is_admin:
            cursor = conn.execute("SELECT COUNT(*) FROM messages WHERE order_id = ? AND is_admin = 0 AND is_read = 0", (order_id,))
        else:
            cursor = conn.execute("SELECT COUNT(*) FROM messages WHERE order_id = ? AND is_admin = 1 AND is_read = 0", (order_id,))
        return cursor.fetchone()[0]


# ==================== БРОШЕННЫЕ КОРЗИНЫ ====================

async def save_abandoned_cart(user_id, stage, cart_data):
    with get_connection() as conn:
        conn.execute("DELETE FROM abandoned_carts WHERE user_id = ? AND recovered = 0", (user_id,))
        conn.execute("""
            INSERT INTO abandoned_carts (user_id, stage, cart_data) VALUES (?, ?, ?)
        """, (user_id, stage, cart_data))
        conn.commit()
        await create_alert('abandoned_cart', user_id, None, f"🛒 Брошена корзина: {stage}", priority=1)

async def get_abandoned_carts(hours=24):
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT ac.*, u.full_name, u.username
            FROM abandoned_carts ac LEFT JOIN users u ON ac.user_id = u.user_id
            WHERE ac.recovered = 0 AND ac.created_at > datetime('now', ?)
            ORDER BY ac.created_at DESC
        """, (f'-{hours} hours',))
        return [dict(row) for row in cursor.fetchall()]


# ==================== СТАТИСТИКА ====================

async def get_stats():
    with get_connection() as conn:
        u_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        o_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        money = conn.execute("SELECT COALESCE(SUM(price), 0) FROM orders WHERE status = 'done'").fetchone()[0]
        return u_count, o_count, money

async def get_detailed_stats():
    with get_connection() as conn:
        stats = {}
        stats['total_users'] = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        stats['active_today'] = conn.execute("SELECT COUNT(*) FROM users WHERE last_seen > datetime('now', '-1 day')").fetchone()[0]
        stats['active_week'] = conn.execute("SELECT COUNT(*) FROM users WHERE last_seen > datetime('now', '-7 days')").fetchone()[0]
        stats['new_today'] = conn.execute("SELECT COUNT(*) FROM users WHERE first_seen > datetime('now', '-1 day')").fetchone()[0]
        stats['total_orders'] = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        stats['new_orders'] = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'new'").fetchone()[0]
        stats['in_progress'] = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'in_progress'").fetchone()[0]
        stats['completed'] = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'done'").fetchone()[0]
        stats['total_revenue'] = conn.execute("SELECT COALESCE(SUM(price), 0) FROM orders WHERE status = 'done'").fetchone()[0]
        stats['today_revenue'] = conn.execute("SELECT COALESCE(SUM(price), 0) FROM orders WHERE status = 'done' AND completed_at > datetime('now', '-1 day')").fetchone()[0]
        stats['pending_revenue'] = conn.execute("SELECT COALESCE(SUM(price), 0) FROM orders WHERE status NOT IN ('done', 'cancelled')").fetchone()[0]
        stats['unread_alerts'] = conn.execute("SELECT COUNT(*) FROM admin_alerts WHERE is_read = 0").fetchone()[0]
        stats['abandoned_carts'] = conn.execute("SELECT COUNT(*) FROM abandoned_carts WHERE recovered = 0 AND created_at > datetime('now', '-24 hours')").fetchone()[0]
        return stats

async def get_online_users():
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM users WHERE last_seen > datetime('now', '-5 minutes') ORDER BY last_seen DESC
        """)
        return [dict(row) for row in cursor.fetchall()]

async def get_hot_leads():
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT u.*, (SELECT COUNT(*) FROM user_actions WHERE user_id = u.user_id AND action_type = 'view_price') as price_views
            FROM users u
            WHERE u.orders_count = 0
            AND u.user_id IN (SELECT DISTINCT user_id FROM user_actions WHERE action_type = 'view_price' AND timestamp > datetime('now', '-7 days'))
            ORDER BY u.last_seen DESC LIMIT 20
        """)
        return [dict(row) for row in cursor.fetchall()]


# ==================== НАСТРОЙКИ ====================

async def get_setting(key):
    with get_connection() as conn:
        cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None

async def set_setting(key, value):
    with get_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()


# ==================== ТРАНЗАКЦИИ ====================

async def add_transaction(user_id, order_id, amount, tx_type, reason):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO transactions (user_id, order_id, amount, type, reason) VALUES (?, ?, ?, ?, ?)
        """, (user_id, order_id, amount, tx_type, reason))
        conn.commit()

async def get_transactions(user_id, limit=20):
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
        return [dict(row) for row in cursor.fetchall()]


# ==================== ОТЗЫВЫ ====================

async def add_review(user_id, text, order_id=None, rating=5):
    with get_connection() as conn:
        conn.execute("INSERT INTO reviews (user_id, order_id, rating, text) VALUES (?, ?, ?, ?)",
                    (user_id, order_id, rating, text))
        conn.commit()

async def get_reviews(limit=50):
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT r.*, u.full_name, u.username
            FROM reviews r LEFT JOIN users u ON r.user_id = u.user_id
            ORDER BY r.created_at DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
