"""
📊 LIVE DASHBOARD - Обновление статуса в канале
"""
import logging
from datetime import datetime
from telegram.ext import Application
from telegram.constants import ParseMode

from config import LOG_CHANNEL_ID
from database import core as db

logger = logging.getLogger(__name__)


class LiveDashboard:
    """Живой дашборд в канале логов"""

    def __init__(self):
        self.message_id = None
        self.app = None

    def attach(self, app: Application):
        """Подключение к приложению"""
        self.app = app

        # Запускаем периодическое обновление
        if app.job_queue:
            app.job_queue.run_repeating(
                self.update_dashboard,
                interval=60,  # Каждую минуту
                first=10,
                name='dashboard_update'
            )
            logger.info("📊 Dashboard job scheduled")

    async def update_dashboard(self, context):
        """Обновление дашборда"""
        if not LOG_CHANNEL_ID:
            return

        try:
            stats = await db.get_detailed_stats()
            online = await db.get_online_users()
            alerts = await db.get_unread_alerts(3)

            now = datetime.now().strftime('%H:%M:%S')

            text = f"📊 <b>LIVE DASHBOARD</b>\n"
            text += f"🕐 Обновлено: {now}\n"
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"

            # Онлайн
            text += f"🟢 <b>Онлайн:</b> {len(online)}\n"
            if online:
                names = [u.get('full_name', 'Аноним')[:15] for u in online[:3]]
                text += f"   {', '.join(names)}\n"
            text += "\n"

            # Статистика
            text += f"👥 Пользователей: <b>{stats['total_users']}</b>\n"
            text += f"📦 Заказов: <b>{stats['total_orders']}</b>\n"
            text += f"🆕 Новых: <b>{stats['new_orders']}</b>\n"
            text += f"⚙️ В работе: <b>{stats['in_progress']}</b>\n\n"

            text += f"💰 Выручка: <b>{stats['total_revenue']:,}₽</b>\n"
            text += f"📈 Сегодня: <b>{stats['today_revenue']:,}₽</b>\n\n"

            # Алерты
            if alerts:
                text += f"🔔 <b>Алерты ({stats['unread_alerts']}):</b>\n"
                for a in alerts:
                    text += f"   • {a['message'][:40]}\n"
                text += "\n"

            # Брошенные корзины
            if stats.get('abandoned_carts', 0) > 0:
                text += f"🛒 Брошенных корзин: <b>{stats['abandoned_carts']}</b>\n"

            text += "\n━━━━━━━━━━━━━━━━━━━━\n"
            text += "🤖 GipseBot | /admin"

            # Отправляем или обновляем сообщение
            if self.message_id:
                try:
                    await context.bot.edit_message_text(
                        text,
                        chat_id=LOG_CHANNEL_ID,
                        message_id=self.message_id,
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    # Сообщение не найдено или не изменилось, отправляем новое
                    msg = await context.bot.send_message(
                        LOG_CHANNEL_ID,
                        text,
                        parse_mode=ParseMode.HTML
                    )
                    self.message_id = msg.message_id
            else:
                msg = await context.bot.send_message(
                    LOG_CHANNEL_ID,
                    text,
                    parse_mode=ParseMode.HTML
                )
                self.message_id = msg.message_id

        except Exception as e:
            logger.error(f"Dashboard update error: {e}")
