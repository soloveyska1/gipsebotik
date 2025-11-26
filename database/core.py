"""
🗄️ БАЗА ДАННЫХ САЛУНА
Все данные о гостях, контрактах и золоте
"""
import sqlite3
import logging
import json
from datetime import datetime, timedelta
from config import DB_PATH, RANKS, NEW_USER_BONUS

logger = logging.getLogger(__name__)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Инициализация базы данных салуна"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # ═══════════════════════════════════════════════════════════
        # 👤 ГОСТИ САЛУНА (пользователи)
        # ═══════════════════════════════════════════════════════════
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,

                -- Экономика
                gold INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0,

                -- Статистика
                orders_count INTEGER DEFAULT 0,
                completed_orders INTEGER DEFAULT 0,

                -- Ранг и статус
                rank TEXT DEFAULT 'newcomer',
                is_banned INTEGER DEFAULT 0,
                ban_reason TEXT,

                -- Рефералка
                referrer_id INTEGER DEFAULT 0,
                referrals_count INTEGER DEFAULT 0,
                referral_earnings INTEGER DEFAULT 0,

                -- Достижения (JSON список)
                achievements TEXT DEFAULT '[]',

                -- Ежедневный бонус
                last_daily_bonus TIMESTAMP,
                daily_streak INTEGER DEFAULT 0,

                -- Метаданные
                notes TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_action TEXT
            )
        """)

        # ═══════════════════════════════════════════════════════════
        # 📦 КОНТРАКТЫ (заказы)
        # ═══════════════════════════════════════════════════════════
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,

                -- Информация о заказе
                service_type TEXT,
                service_name TEXT,
                topic TEXT,
                description TEXT,

                -- Сроки
                urgency TEXT,
                deadline TEXT,

                -- Цена
                base_price INTEGER DEFAULT 0,
                final_price INTEGER DEFAULT 0,
                gold_used INTEGER DEFAULT 0,
                discount_percent INTEGER DEFAULT 0,

                -- Допы (JSON)
                upsells TEXT DEFAULT '[]',

                -- Файлы (JSON список file_id)
                files TEXT DEFAULT '[]',
                result_files TEXT DEFAULT '[]',

                -- Статус
                status TEXT DEFAULT 'new',
                payment_status TEXT DEFAULT 'pending',

                -- Управление
                priority INTEGER DEFAULT 0,
                assigned_to TEXT,
                internal_notes TEXT DEFAULT '',

                -- Даты
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,

                -- Оценка
                rating INTEGER,
                feedback TEXT
            )
        """)

        # ═══════════════════════════════════════════════════════════
        # 💬 СООБЩЕНИЯ ЧАТА
        # ═══════════════════════════════════════════════════════════
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                sender_id INTEGER,
                is_admin INTEGER DEFAULT 0,

                msg_type TEXT DEFAULT 'text',
                content TEXT,
                file_id TEXT,

                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ═══════════════════════════════════════════════════════════
        # 🪙 ТРАНЗАКЦИИ ЗОЛОТА
        # ═══════════════════════════════════════════════════════════
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gold_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,

                type TEXT,  -- bonus, referral, order, promo, admin
                reason TEXT,
                order_id INTEGER,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ═══════════════════════════════════════════════════════════
        # 🎁 ПРОМОКОДЫ
        # ═══════════════════════════════════════════════════════════
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,

                type TEXT,  -- gold, discount
                value INTEGER,  -- сумма золота или % скидки

                max_uses INTEGER DEFAULT 0,  -- 0 = безлимит
                used_count INTEGER DEFAULT 0,

                valid_from TIMESTAMP,
                valid_until TIMESTAMP,

                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ═══════════════════════════════════════════════════════════
        # 📜 ИСПОЛЬЗОВАНИЕ ПРОМОКОДОВ
        # ═══════════════════════════════════════════════════════════
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS promo_uses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                promo_id INTEGER,
                user_id INTEGER,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ═══════════════════════════════════════════════════════════
        # ⭐ ОТЗЫВЫ
        # ═══════════════════════════════════════════════════════════
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

        # ═══════════════════════════════════════════════════════════
        # 🔔 АЛЕРТЫ ДЛЯ ШЕРИФА
        # ═══════════════════════════════════════════════════════════
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                user_id INTEGER,
                order_id INTEGER,

                message TEXT,
                priority INTEGER DEFAULT 0,

                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ═══════════════════════════════════════════════════════════
        # 📊 ЛОГ ДЕЙСТВИЙ
        # ═══════════════════════════════════════════════════════════
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
    logger.info("🗄️ База данных салуна готова!")


# ═══════════════════════════════════════════════════════════
# 👤 РАБОТА С ГОСТЯМИ
# ═══════════════════════════════════════════════════════════

async def get_user(user_id: int) -> dict:
    """Получить данные гостя"""
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


async def create_user(user_id: int, username: str, full_name: str, referrer_id: int = 0) -> bool:
    """Создать нового гостя"""
    with get_connection() as conn:
        # Проверяем существует ли
        cursor = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            # Обновляем last_seen
            conn.execute("""
                UPDATE users SET last_seen = ?, username = ?, full_name = ?
                WHERE user_id = ?
            """, (datetime.now(), username, full_name, user_id))
            conn.commit()
            return False

        # Создаём нового
        conn.execute("""
            INSERT INTO users (user_id, username, full_name, gold, referrer_id)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, username, full_name, NEW_USER_BONUS, referrer_id))
        conn.commit()

        # Записываем транзакцию золота
        await add_gold_transaction(user_id, NEW_USER_BONUS, 'bonus', 'Приветственный бонус')

        # Создаём алерт
        await create_alert('new_user', user_id, None, f"🆕 Новый гость: {full_name}", priority=1)

        # Если есть реферер - обновляем его статистику
        if referrer_id:
            conn.execute("""
                UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id = ?
            """, (referrer_id,))
            conn.commit()

            # Проверяем достижение
            await check_achievement(referrer_id, 'first_referral')

        return True


async def update_user(user_id: int, **fields):
    """Обновить поля пользователя"""
    if not fields:
        return
    with get_connection() as conn:
        set_clause = ', '.join(f"{k} = ?" for k in fields.keys())
        values = list(fields.values()) + [user_id]
        conn.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", values)
        conn.commit()


async def update_last_seen(user_id: int, action: str = None):
    """Обновить время последнего визита"""
    with get_connection() as conn:
        conn.execute("""
            UPDATE users SET last_seen = ?, last_action = ? WHERE user_id = ?
        """, (datetime.now(), action, user_id))
        conn.commit()


async def get_user_rank(user_id: int) -> dict:
    """Получить текущий ранг пользователя"""
    user = await get_user(user_id)
    if not user:
        return RANKS['newcomer']

    total_spent = user.get('total_spent', 0)

    # Определяем ранг по сумме трат
    current_rank = RANKS['newcomer']
    for rank_key, rank_data in RANKS.items():
        if total_spent >= rank_data['min_spent']:
            current_rank = rank_data
            current_rank['key'] = rank_key

    return current_rank


async def ban_user(user_id: int, reason: str = ""):
    """Забанить гостя"""
    with get_connection() as conn:
        conn.execute("""
            UPDATE users SET is_banned = 1, ban_reason = ? WHERE user_id = ?
        """, (reason, user_id))
        conn.commit()
    await create_alert('ban', user_id, None, f"🚫 Забанен: {reason}")


async def unban_user(user_id: int):
    """Разбанить гостя"""
    with get_connection() as conn:
        conn.execute("UPDATE users SET is_banned = 0, ban_reason = NULL WHERE user_id = ?", (user_id,))
        conn.commit()


async def search_users(query: str) -> list:
    """Поиск пользователей"""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM users
            WHERE full_name LIKE ? OR username LIKE ? OR CAST(user_id AS TEXT) LIKE ?
            ORDER BY last_seen DESC LIMIT 20
        """, (f'%{query}%', f'%{query}%', f'%{query}%'))
        return [dict(row) for row in cursor.fetchall()]


async def get_all_users(limit: int = 50, offset: int = 0, filter_type: str = None) -> list:
    """Получить список пользователей"""
    with get_connection() as conn:
        query = "SELECT * FROM users"
        params = []

        if filter_type == 'active':
            query += " WHERE last_seen > datetime('now', '-7 days')"
        elif filter_type == 'with_orders':
            query += " WHERE orders_count > 0"
        elif filter_type == 'vip':
            query += " WHERE total_spent >= 15000"
        elif filter_type == 'banned':
            query += " WHERE is_banned = 1"

        query += " ORDER BY last_seen DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


# ═══════════════════════════════════════════════════════════
# 🪙 РАБОТА С ЗОЛОТОМ
# ═══════════════════════════════════════════════════════════

async def add_gold(user_id: int, amount: int, tx_type: str, reason: str, order_id: int = None):
    """Начислить золото"""
    with get_connection() as conn:
        conn.execute("UPDATE users SET gold = gold + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
    await add_gold_transaction(user_id, amount, tx_type, reason, order_id)


async def spend_gold(user_id: int, amount: int, order_id: int = None) -> bool:
    """Списать золото"""
    user = await get_user(user_id)
    if not user or user['gold'] < amount:
        return False

    with get_connection() as conn:
        conn.execute("UPDATE users SET gold = gold - ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
    await add_gold_transaction(user_id, -amount, 'order', 'Оплата заказа', order_id)
    return True


async def add_gold_transaction(user_id: int, amount: int, tx_type: str, reason: str, order_id: int = None):
    """Записать транзакцию золота"""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO gold_transactions (user_id, amount, type, reason, order_id)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, amount, tx_type, reason, order_id))
        conn.commit()


async def get_gold_history(user_id: int, limit: int = 20) -> list:
    """История транзакций золота"""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM gold_transactions WHERE user_id = ?
            ORDER BY created_at DESC LIMIT ?
        """, (user_id, limit))
        return [dict(row) for row in cursor.fetchall()]


# ═══════════════════════════════════════════════════════════
# 📦 РАБОТА С ЗАКАЗАМИ
# ═══════════════════════════════════════════════════════════

async def create_order(data: dict) -> int:
    """Создать новый заказ"""
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO orders (
                user_id, service_type, service_name, topic, description,
                urgency, deadline, base_price, final_price, gold_used,
                discount_percent, upsells, files
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['user_id'],
            data.get('service_type', ''),
            data.get('service_name', ''),
            data.get('topic', ''),
            data.get('description', ''),
            data.get('urgency', 'normal'),
            data.get('deadline', ''),
            data.get('base_price', 0),
            data.get('final_price', 0),
            data.get('gold_used', 0),
            data.get('discount_percent', 0),
            json.dumps(data.get('upsells', [])),
            json.dumps(data.get('files', []))
        ))
        conn.commit()
        order_id = cursor.lastrowid

        # Обновляем счётчик заказов
        conn.execute("UPDATE users SET orders_count = orders_count + 1 WHERE user_id = ?",
                    (data['user_id'],))
        conn.commit()

        # Создаём алерт
        await create_alert(
            'new_order', data['user_id'], order_id,
            f"🔥 Новый контракт #{order_id}: {data.get('service_name', 'Заказ')}",
            priority=2
        )

        # Проверяем достижение первого заказа
        await check_achievement(data['user_id'], 'first_order')

        return order_id


async def get_order(order_id: int) -> dict:
    """Получить заказ по ID"""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT o.*, u.full_name, u.username, u.gold as user_gold
            FROM orders o
            LEFT JOIN users u ON o.user_id = u.user_id
            WHERE o.id = ?
        """, (order_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


async def get_user_orders(user_id: int, limit: int = 20) -> list:
    """Заказы пользователя"""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM orders WHERE user_id = ?
            ORDER BY created_at DESC LIMIT ?
        """, (user_id, limit))
        return [dict(row) for row in cursor.fetchall()]


async def get_all_orders(status: str = None, limit: int = 50) -> list:
    """Все заказы (для админа)"""
    with get_connection() as conn:
        if status:
            cursor = conn.execute("""
                SELECT o.*, u.full_name, u.username
                FROM orders o LEFT JOIN users u ON o.user_id = u.user_id
                WHERE o.status = ?
                ORDER BY o.priority DESC, o.created_at DESC LIMIT ?
            """, (status, limit))
        else:
            cursor = conn.execute("""
                SELECT o.*, u.full_name, u.username
                FROM orders o LEFT JOIN users u ON o.user_id = u.user_id
                WHERE o.status NOT IN ('completed', 'cancelled')
                ORDER BY o.priority DESC, o.created_at DESC LIMIT ?
            """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


async def update_order(order_id: int, **fields):
    """Обновить заказ"""
    if not fields:
        return
    fields['updated_at'] = datetime.now()
    with get_connection() as conn:
        set_clause = ', '.join(f"{k} = ?" for k in fields.keys())
        values = list(fields.values()) + [order_id]
        conn.execute(f"UPDATE orders SET {set_clause} WHERE id = ?", values)
        conn.commit()


async def complete_order(order_id: int):
    """Завершить заказ"""
    order = await get_order(order_id)
    if not order:
        return

    with get_connection() as conn:
        conn.execute("""
            UPDATE orders SET status = 'completed', completed_at = ? WHERE id = ?
        """, (datetime.now(), order_id))

        # Обновляем статистику пользователя
        conn.execute("""
            UPDATE users SET
                completed_orders = completed_orders + 1,
                total_spent = total_spent + ?
            WHERE user_id = ?
        """, (order['final_price'], order['user_id']))
        conn.commit()

    # Проверяем достижения
    user = await get_user(order['user_id'])
    if user:
        completed = user.get('completed_orders', 0) + 1
        if completed >= 3:
            await check_achievement(order['user_id'], 'three_orders')
        if completed >= 5:
            await check_achievement(order['user_id'], 'five_orders')
        if completed >= 10:
            await check_achievement(order['user_id'], 'ten_orders')

        if user.get('total_spent', 0) + order['final_price'] >= 10000:
            await check_achievement(order['user_id'], 'big_spender')

    # Начисляем бонус рефереру
    if user and user.get('referrer_id'):
        bonus = int(order['final_price'] * 0.1)  # 10%
        if bonus > 0:
            await add_gold(
                user['referrer_id'], bonus, 'referral',
                f"Бонус за заказ друга #{order_id}"
            )


# ═══════════════════════════════════════════════════════════
# 💬 ЧАТ
# ═══════════════════════════════════════════════════════════

async def add_message(order_id: int, sender_id: int, is_admin: bool,
                      content: str, msg_type: str = 'text', file_id: str = None):
    """Добавить сообщение в чат"""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO messages (order_id, sender_id, is_admin, msg_type, content, file_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (order_id, sender_id, 1 if is_admin else 0, msg_type, content, file_id))
        conn.commit()


async def get_messages(order_id: int, limit: int = 50) -> list:
    """Получить сообщения чата"""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM messages WHERE order_id = ?
            ORDER BY created_at ASC LIMIT ?
        """, (order_id, limit))
        return [dict(row) for row in cursor.fetchall()]


async def get_unread_count(order_id: int, for_admin: bool = True) -> int:
    """Количество непрочитанных сообщений"""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT COUNT(*) FROM messages
            WHERE order_id = ? AND is_admin = ? AND is_read = 0
        """, (order_id, 0 if for_admin else 1))
        return cursor.fetchone()[0]


# ═══════════════════════════════════════════════════════════
# 🎁 ПРОМОКОДЫ
# ═══════════════════════════════════════════════════════════

async def create_promo(code: str, promo_type: str, value: int,
                       max_uses: int = 0, valid_days: int = 30) -> int:
    """Создать промокод"""
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO promo_codes (code, type, value, max_uses, valid_until)
            VALUES (?, ?, ?, ?, ?)
        """, (code.upper(), promo_type, value, max_uses,
              datetime.now() + timedelta(days=valid_days)))
        conn.commit()
        return cursor.lastrowid


async def get_promo(code: str) -> dict:
    """Получить промокод"""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM promo_codes WHERE code = ? AND is_active = 1
        """, (code.upper(),))
        row = cursor.fetchone()
        return dict(row) if row else None


async def use_promo(promo_id: int, user_id: int) -> bool:
    """Использовать промокод"""
    with get_connection() as conn:
        # Проверяем не использовал ли уже
        cursor = conn.execute("""
            SELECT id FROM promo_uses WHERE promo_id = ? AND user_id = ?
        """, (promo_id, user_id))
        if cursor.fetchone():
            return False

        # Записываем использование
        conn.execute("""
            INSERT INTO promo_uses (promo_id, user_id) VALUES (?, ?)
        """, (promo_id, user_id))

        # Увеличиваем счётчик
        conn.execute("""
            UPDATE promo_codes SET used_count = used_count + 1 WHERE id = ?
        """, (promo_id,))
        conn.commit()
        return True


# ═══════════════════════════════════════════════════════════
# 🏆 ДОСТИЖЕНИЯ
# ═══════════════════════════════════════════════════════════

async def check_achievement(user_id: int, achievement_key: str) -> bool:
    """Проверить и выдать достижение"""
    from config import ACHIEVEMENTS

    user = await get_user(user_id)
    if not user:
        return False

    achievements = json.loads(user.get('achievements', '[]'))
    if achievement_key in achievements:
        return False  # Уже есть

    achievement = ACHIEVEMENTS.get(achievement_key)
    if not achievement:
        return False

    # Добавляем достижение
    achievements.append(achievement_key)
    with get_connection() as conn:
        conn.execute("""
            UPDATE users SET achievements = ? WHERE user_id = ?
        """, (json.dumps(achievements), user_id))
        conn.commit()

    # Начисляем награду
    if achievement.get('reward', 0) > 0:
        await add_gold(
            user_id, achievement['reward'], 'bonus',
            f"Достижение: {achievement['name']}"
        )

    return True


async def get_user_achievements(user_id: int) -> list:
    """Получить достижения пользователя"""
    user = await get_user(user_id)
    if not user:
        return []
    return json.loads(user.get('achievements', '[]'))


# ═══════════════════════════════════════════════════════════
# 🎰 ЕЖЕДНЕВНЫЙ БОНУС
# ═══════════════════════════════════════════════════════════

async def can_spin_daily(user_id: int) -> bool:
    """Можно ли крутить барабан сегодня"""
    user = await get_user(user_id)
    if not user:
        return False

    last_spin = user.get('last_daily_bonus')
    if not last_spin:
        return True

    # Парсим дату
    if isinstance(last_spin, str):
        try:
            last_spin = datetime.fromisoformat(last_spin)
        except:
            return True

    # Проверяем прошли ли сутки
    return datetime.now() - last_spin > timedelta(hours=24)


async def record_daily_spin(user_id: int, reward: int):
    """Записать результат спина"""
    user = await get_user(user_id)
    if not user:
        return

    # Проверяем streak
    last_spin = user.get('last_daily_bonus')
    streak = user.get('daily_streak', 0)

    if last_spin:
        if isinstance(last_spin, str):
            try:
                last_spin = datetime.fromisoformat(last_spin)
            except:
                last_spin = None

        if last_spin and datetime.now() - last_spin < timedelta(hours=48):
            streak += 1
        else:
            streak = 1
    else:
        streak = 1

    with get_connection() as conn:
        conn.execute("""
            UPDATE users SET last_daily_bonus = ?, daily_streak = ?, gold = gold + ?
            WHERE user_id = ?
        """, (datetime.now(), streak, reward, user_id))
        conn.commit()

    await add_gold_transaction(user_id, reward, 'bonus', f'Ежедневный бонус (streak: {streak})')


# ═══════════════════════════════════════════════════════════
# 🔔 АЛЕРТЫ
# ═══════════════════════════════════════════════════════════

async def create_alert(alert_type: str, user_id: int, order_id: int,
                       message: str, priority: int = 0):
    """Создать алерт"""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO alerts (type, user_id, order_id, message, priority)
            VALUES (?, ?, ?, ?, ?)
        """, (alert_type, user_id, order_id, message, priority))
        conn.commit()


async def get_unread_alerts(limit: int = 20) -> list:
    """Получить непрочитанные алерты"""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT a.*, u.full_name, u.username
            FROM alerts a LEFT JOIN users u ON a.user_id = u.user_id
            WHERE a.is_read = 0
            ORDER BY a.priority DESC, a.created_at DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


async def mark_alerts_read():
    """Отметить все алерты прочитанными"""
    with get_connection() as conn:
        conn.execute("UPDATE alerts SET is_read = 1")
        conn.commit()


# ═══════════════════════════════════════════════════════════
# 📊 СТАТИСТИКА
# ═══════════════════════════════════════════════════════════

async def get_stats() -> dict:
    """Общая статистика салуна"""
    with get_connection() as conn:
        stats = {}

        stats['total_users'] = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        stats['active_today'] = conn.execute("""
            SELECT COUNT(*) FROM users WHERE last_seen > datetime('now', '-1 day')
        """).fetchone()[0]
        stats['new_today'] = conn.execute("""
            SELECT COUNT(*) FROM users WHERE created_at > datetime('now', '-1 day')
        """).fetchone()[0]

        stats['total_orders'] = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        stats['new_orders'] = conn.execute("""
            SELECT COUNT(*) FROM orders WHERE status = 'new'
        """).fetchone()[0]
        stats['in_progress'] = conn.execute("""
            SELECT COUNT(*) FROM orders WHERE status IN ('in_progress', 'checking')
        """).fetchone()[0]
        stats['completed'] = conn.execute("""
            SELECT COUNT(*) FROM orders WHERE status = 'completed'
        """).fetchone()[0]

        stats['total_revenue'] = conn.execute("""
            SELECT COALESCE(SUM(final_price), 0) FROM orders WHERE status = 'completed'
        """).fetchone()[0]
        stats['today_revenue'] = conn.execute("""
            SELECT COALESCE(SUM(final_price), 0) FROM orders
            WHERE status = 'completed' AND completed_at > datetime('now', '-1 day')
        """).fetchone()[0]

        stats['unread_alerts'] = conn.execute("""
            SELECT COUNT(*) FROM alerts WHERE is_read = 0
        """).fetchone()[0]

        return stats


async def get_online_users() -> list:
    """Пользователи онлайн (5 минут)"""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM users WHERE last_seen > datetime('now', '-5 minutes')
            ORDER BY last_seen DESC
        """)
        return [dict(row) for row in cursor.fetchall()]


# ═══════════════════════════════════════════════════════════
# 📜 ЛОГ ДЕЙСТВИЙ
# ═══════════════════════════════════════════════════════════

async def log_action(user_id: int, action: str, data: str = None):
    """Записать действие пользователя"""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO action_log (user_id, action, data) VALUES (?, ?, ?)
        """, (user_id, action, data))
        conn.commit()


async def get_user_actions(user_id: int, limit: int = 50) -> list:
    """История действий пользователя"""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM action_log WHERE user_id = ?
            ORDER BY created_at DESC LIMIT ?
        """, (user_id, limit))
        return [dict(row) for row in cursor.fetchall()]


async def get_recent_actions(limit: int = 100) -> list:
    """Последние действия всех пользователей"""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT a.*, u.full_name, u.username
            FROM action_log a LEFT JOIN users u ON a.user_id = u.user_id
            ORDER BY a.created_at DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


# ═══════════════════════════════════════════════════════════
# 📊 РАСШИРЕННАЯ СТАТИСТИКА (ДЛЯ АДМИНКИ)
# ═══════════════════════════════════════════════════════════

async def get_detailed_stats() -> dict:
    """Детальная статистика для админки"""
    with get_connection() as conn:
        stats = {}

        stats['total_users'] = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        stats['new_today'] = conn.execute("""
            SELECT COUNT(*) FROM users WHERE created_at > datetime('now', '-1 day')
        """).fetchone()[0]
        stats['active_today'] = conn.execute("""
            SELECT COUNT(*) FROM users WHERE last_seen > datetime('now', '-1 day')
        """).fetchone()[0]
        stats['active_week'] = conn.execute("""
            SELECT COUNT(*) FROM users WHERE last_seen > datetime('now', '-7 days')
        """).fetchone()[0]

        stats['total_orders'] = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        stats['new_orders'] = conn.execute("""
            SELECT COUNT(*) FROM orders WHERE status = 'new'
        """).fetchone()[0]
        stats['in_progress'] = conn.execute("""
            SELECT COUNT(*) FROM orders WHERE status IN ('in_progress', 'checking')
        """).fetchone()[0]
        stats['completed'] = conn.execute("""
            SELECT COUNT(*) FROM orders WHERE status = 'completed'
        """).fetchone()[0]

        stats['total_revenue'] = conn.execute("""
            SELECT COALESCE(SUM(final_price), 0) FROM orders WHERE status = 'completed'
        """).fetchone()[0]
        stats['today_revenue'] = conn.execute("""
            SELECT COALESCE(SUM(final_price), 0) FROM orders
            WHERE status = 'completed' AND completed_at > datetime('now', '-1 day')
        """).fetchone()[0]
        stats['pending_revenue'] = conn.execute("""
            SELECT COALESCE(SUM(final_price), 0) FROM orders
            WHERE status NOT IN ('completed', 'cancelled')
        """).fetchone()[0]

        stats['unread_alerts'] = conn.execute("""
            SELECT COUNT(*) FROM alerts WHERE is_read = 0
        """).fetchone()[0]

        stats['abandoned_carts'] = conn.execute("""
            SELECT COUNT(*) FROM action_log
            WHERE action = 'abandoned_cart' AND created_at > datetime('now', '-2 days')
        """).fetchone()[0]

        return stats


# ═══════════════════════════════════════════════════════════
# 💬 ЧАТ (ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ)
# ═══════════════════════════════════════════════════════════

async def get_chat_history(order_id: int, limit: int = 50) -> list:
    """История чата по заказу"""
    return await get_messages(order_id, limit)


async def add_chat_message(order_id: int, sender_id: int, is_admin: bool,
                           msg_type: str, content: str, file_id: str = None):
    """Добавить сообщение в чат (алиас для add_message)"""
    await add_message(order_id, sender_id, is_admin, content, msg_type, file_id)


async def get_unread_messages_count(order_id: int, is_admin: bool = True) -> int:
    """Количество непрочитанных сообщений"""
    return await get_unread_count(order_id, is_admin)


# ═══════════════════════════════════════════════════════════
# 📦 ЗАКАЗЫ (ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ)
# ═══════════════════════════════════════════════════════════

async def update_order_status(order_id: int, status: str):
    """Обновить статус заказа"""
    await update_order(order_id, status=status)


# ═══════════════════════════════════════════════════════════
# 🔥 ГОРЯЧИЕ ЛИДЫ И ВОРОНКА
# ═══════════════════════════════════════════════════════════

async def track_funnel(user_id: int, step: str):
    """Отслеживание воронки продаж"""
    await log_action(user_id, f"funnel_{step}", step)


async def get_hot_leads(limit: int = 20) -> list:
    """Горячие лиды - смотрели прайс но не заказали"""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT u.*,
                   (SELECT COUNT(*) FROM action_log WHERE user_id = u.user_id
                    AND action LIKE '%price%') as price_views
            FROM users u
            WHERE u.orders_count = 0
              AND u.last_seen > datetime('now', '-7 days')
              AND EXISTS (SELECT 1 FROM action_log WHERE user_id = u.user_id
                          AND action LIKE '%price%')
            ORDER BY u.last_seen DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


async def save_abandoned_cart(user_id: int, stage: str, data: str = None):
    """Сохранить брошенную корзину"""
    await log_action(user_id, 'abandoned_cart', f"{stage}:{data}" if data else stage)


async def get_abandoned_carts(hours: int = 48, limit: int = 20) -> list:
    """Получить брошенные корзины"""
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT a.*, u.full_name, u.username
            FROM action_log a
            JOIN users u ON a.user_id = u.user_id
            WHERE a.action = 'abandoned_cart'
              AND a.created_at > datetime('now', '-' || ? || ' hours')
            ORDER BY a.created_at DESC LIMIT ?
        """, (hours, limit))
        results = []
        for row in cursor.fetchall():
            r = dict(row)
            # Парсим stage из data
            data = r.get('data', '')
            if ':' in data:
                r['stage'] = data.split(':')[0]
            else:
                r['stage'] = data
            results.append(r)
        return results


# ═══════════════════════════════════════════════════════════
# 👤 ПОЛЬЗОВАТЕЛИ (ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ)
# ═══════════════════════════════════════════════════════════

async def add_user(user_id: int, username: str, full_name: str, referrer_id: int = 0) -> bool:
    """Алиас для create_user (совместимость)"""
    return await create_user(user_id, username, full_name, referrer_id)


async def update_user_field(user_id: int, field: str, value):
    """Обновить одно поле пользователя"""
    await update_user(user_id, **{field: value})


async def get_transactions(user_id: int, limit: int = 20) -> list:
    """Алиас для get_gold_history (совместимость)"""
    return await get_gold_history(user_id, limit)


async def unban_user(user_id: int):
    """Разбанить пользователя (явный алиас)"""
    with get_connection() as conn:
        conn.execute("UPDATE users SET is_banned = 0, ban_reason = NULL WHERE user_id = ?", (user_id,))
        conn.commit()


async def mark_all_alerts_read():
    """Отметить все алерты прочитанными (алиас)"""
    await mark_alerts_read()


# ═══════════════════════════════════════════════════════════
# ⭐ ОТЗЫВЫ (ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ)
# ═══════════════════════════════════════════════════════════

async def add_review(user_id: int, text: str, order_id: int = None, rating: int = 5):
    """Добавить отзыв"""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO reviews (user_id, order_id, rating, text)
            VALUES (?, ?, ?, ?)
        """, (user_id, order_id, rating, text))
        conn.commit()


async def get_reviews(limit: int = 20, published_only: bool = True) -> list:
    """Получить отзывы"""
    with get_connection() as conn:
        query = """
            SELECT r.*, u.full_name, u.username
            FROM reviews r
            LEFT JOIN users u ON r.user_id = u.user_id
        """
        if published_only:
            query += " WHERE r.is_published = 1"
        query += " ORDER BY r.created_at DESC LIMIT ?"

        cursor = conn.execute(query, (limit,))
        return [dict(row) for row in cursor.fetchall()]
