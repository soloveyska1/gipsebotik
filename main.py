import logging
import os
import asyncio
import re
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)

# Импорты конфига и базы
from config import BOT_TOKEN, LOGS_DIR, ADMIN_SECRET_CODE
from database.core import init_db, create_promo_code

# Импорты хендлеров
from handlers import client
from handlers import admin

# Настройка логов
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Отключаем лишний шум от библиотек
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)


async def init_promo_codes():
    """Инициализация промокодов при старте."""
    # Пасхалка FIRSTSHOT — 50₽ бонус (небольшой, но приятно)
    await create_promo_code("FIRSTSHOT", discount_percent=0, bonus_amount=50, max_uses=1000)
    logging.info("Промокод FIRSTSHOT создан")


def main():
    print("🔌 Подключаем базу данных...")
    init_db()

    print("🚀 Инициализация бота...")
    app = Application.builder().token(BOT_TOKEN).build()

    # === ПОСВЯЩЕНИЕ В КОВБОИ: НОВЫЕ ОБРАБОТЧИКИ ===
    app.add_handler(CallbackQueryHandler(client.toggle_initiation_agree, pattern="^init_toggle_agree$"))
    app.add_handler(CallbackQueryHandler(client.accept_initiation, pattern="^init_accept$"))
    app.add_handler(CallbackQueryHandler(client.initiation_not_agreed, pattern="^init_not_agreed$"))
    app.add_handler(CallbackQueryHandler(client.show_initiation_details, pattern="^init_details$"))
    app.add_handler(CallbackQueryHandler(client.show_initiation_welcome, pattern="^init_back$"))
    # Традиции из профиля
    app.add_handler(CallbackQueryHandler(client.show_traditions, pattern="^traditions$"))
    app.add_handler(CallbackQueryHandler(client.show_traditions_full, pattern="^traditions_full$"))

    # === СТАРЫЕ ОБРАБОТЧИКИ (обратная совместимость) ===
    app.add_handler(CallbackQueryHandler(client.show_salon_code_short, pattern="^code_read_full$"))
    app.add_handler(CallbackQueryHandler(client.show_salon_code_full, pattern="^code_read_details$"))
    app.add_handler(CallbackQueryHandler(client.show_salon_code_checkboxes, pattern="^code_accept_start$"))
    app.add_handler(CallbackQueryHandler(client.toggle_checkbox, pattern="^code_check_"))
    app.add_handler(CallbackQueryHandler(client.code_not_ready, pattern="^code_not_ready$"))
    app.add_handler(CallbackQueryHandler(client.accept_salon_code, pattern="^code_final_accept$"))
    app.add_handler(CallbackQueryHandler(client.show_code_of_honor, pattern="^code_honor$"))
    app.add_handler(CallbackQueryHandler(client.show_code_full_readonly, pattern="^code_view_full$"))

    # === КЛИЕНТ: ГЛАВНОЕ МЕНЮ И ПРОФИЛЬ ===
    app.add_handler(CommandHandler("start", client.start))
    app.add_handler(CallbackQueryHandler(client.start, pattern="^home$"))
    app.add_handler(CallbackQueryHandler(client.profile, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(client.partners, pattern="^partners$"))
    app.add_handler(CallbackQueryHandler(client.my_history, pattern="^my_history$"))
    app.add_handler(CallbackQueryHandler(client.my_transactions, pattern="^my_transactions$"))
    app.add_handler(CallbackQueryHandler(client.my_order, pattern="^my_order_"))
    app.add_handler(CallbackQueryHandler(client.cli_approve, pattern="^cli_approve_"))
    app.add_handler(CallbackQueryHandler(client.cli_delete, pattern="^cli_delete_"))

    # Дневной бонус / Сейф
    app.add_handler(CallbackQueryHandler(client.play_daily_bonus, pattern="^daily_bonus$"))
    app.add_handler(CallbackQueryHandler(client.open_safe, pattern="^my_safe$"))
    app.add_handler(CallbackQueryHandler(client.send_safe_file, pattern="^get_file_msg_"))

    # Мини-игры
    app.add_handler(CallbackQueryHandler(client.start_duel, pattern="^duel_start$"))
    app.add_handler(CallbackQueryHandler(client.resolve_duel, pattern="^duel_pick_"))
    app.add_handler(CallbackQueryHandler(client.draw_deadline_oracle, pattern="^deadline_oracle$"))

    # Ввод промокода
    promo_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(client.ask_promo_code, pattern="^enter_promo$")],
        states={
            client.PROMO_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, client.submit_promo_code)]
        },
        fallbacks=[CallbackQueryHandler(client.profile, pattern="^profile$")]
    )
    app.add_handler(promo_conv)

    # Прайс-лист
    app.add_handler(CallbackQueryHandler(client.show_price_list, pattern="^price_list$"))
    app.add_handler(CallbackQueryHandler(client.show_price_card, pattern="^price_srv_"))

    # === ОТЗЫВЫ ===
    review_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(client.ask_review, pattern="^write_review$")],
        states={
            client.REVIEW_STATE: [MessageHandler(filters.TEXT | filters.PHOTO, client.submit_review)]
        },
        fallbacks=[CallbackQueryHandler(client.cancel_review, pattern="^home$")]
    )
    app.add_handler(review_conv)

    # "Пасхалка" на слово "спасибо"
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, client.handle_thanks))

    # === СУПЕР-АДМИНКА ===

    # Секретная команда входа
    app.add_handler(CommandHandler(f"admin_{ADMIN_SECRET_CODE}", admin.admin_secret_entry))

    # Главная панель
    app.add_handler(CallbackQueryHandler(admin.show_admin_panel, pattern="^adm_panel$"))
    app.add_handler(CallbackQueryHandler(admin.admin_refresh, pattern="^adm_refresh$"))

    # Клиенты
    app.add_handler(CallbackQueryHandler(admin.show_clients, pattern="^adm_clients$"))
    app.add_handler(CallbackQueryHandler(admin.clients_filter, pattern="^adm_cli_filter_"))
    app.add_handler(CallbackQueryHandler(admin.clients_page, pattern="^adm_cli_page_"))
    app.add_handler(CallbackQueryHandler(admin.show_client_card, pattern="^adm_client_"))
    app.add_handler(CallbackQueryHandler(admin.toggle_ban, pattern="^adm_ban_"))
    app.add_handler(CallbackQueryHandler(admin.toggle_watch, pattern="^adm_watch_"))

    # Баланс клиента
    balance_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin.ask_balance_change, pattern="^adm_balance_")],
        states={
            admin.WAITING_BALANCE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin.process_balance_change)]
        },
        fallbacks=[CallbackQueryHandler(admin.show_admin_panel, pattern="^adm_panel$")]
    )
    app.add_handler(balance_conv)

    # Заметки о клиентах
    note_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin.ask_note, pattern="^adm_note_")],
        states={
            admin.WAITING_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin.process_note)]
        },
        fallbacks=[CallbackQueryHandler(admin.show_admin_panel, pattern="^adm_panel$")]
    )
    app.add_handler(note_conv)

    # Заказы
    app.add_handler(CallbackQueryHandler(admin.show_orders, pattern="^adm_orders$"))
    app.add_handler(CallbackQueryHandler(admin.orders_filter, pattern="^adm_ord_filter_"))
    app.add_handler(CallbackQueryHandler(admin.orders_page, pattern="^adm_ord_page_"))
    app.add_handler(CallbackQueryHandler(admin.show_order_card, pattern="^adm_order_"))
    app.add_handler(CallbackQueryHandler(admin.change_order_status, pattern="^adm_ord_status_"))

    # Финансы
    app.add_handler(CallbackQueryHandler(admin.show_finance, pattern="^adm_finance$"))
    app.add_handler(CallbackQueryHandler(admin.show_finance_by_services, pattern="^adm_fin_services$"))

    # Аналитика
    app.add_handler(CallbackQueryHandler(admin.show_analytics, pattern="^adm_analytics$"))
    app.add_handler(CallbackQueryHandler(admin.show_referral_stats, pattern="^adm_an_referrals$"))

    # Рассылка
    app.add_handler(CallbackQueryHandler(admin.show_broadcast, pattern="^adm_broadcast$"))
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin.start_broadcast, pattern="^adm_bc_(all|with_orders|without_orders|vip)$")],
        states={
            admin.WAITING_BROADCAST_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin.process_broadcast_text)]
        },
        fallbacks=[CallbackQueryHandler(admin.show_admin_panel, pattern="^adm_panel$")]
    )
    app.add_handler(broadcast_conv)
    app.add_handler(CallbackQueryHandler(admin.send_broadcast, pattern="^adm_bc_send_"))

    # Промокоды
    app.add_handler(CallbackQueryHandler(admin.show_promos, pattern="^adm_promos$"))
    app.add_handler(CallbackQueryHandler(admin.show_promo_stats, pattern="^adm_promo_stats$"))
    app.add_handler(CallbackQueryHandler(admin.toggle_promo, pattern="^adm_promo_toggle_"))
    promo_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin.start_promo_create, pattern="^adm_promo_create$")],
        states={
            admin.WAITING_PROMO_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin.process_promo_code)],
            admin.WAITING_PROMO_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin.process_promo_amount)]
        },
        fallbacks=[CallbackQueryHandler(admin.show_admin_panel, pattern="^adm_panel$")]
    )
    app.add_handler(promo_conv)

    # Уведомления
    app.add_handler(CallbackQueryHandler(admin.show_notifications, pattern="^adm_notifications$"))
    app.add_handler(CallbackQueryHandler(admin.toggle_notification, pattern="^adm_notif_toggle_"))

    # Настройки
    app.add_handler(CallbackQueryHandler(admin.show_settings, pattern="^adm_settings$"))
    app.add_handler(CallbackQueryHandler(admin.backup_database, pattern="^adm_set_backup$"))

    # Чат с клиентом
    chat_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin.start_chat, pattern="^adm_chat_\\d+$")],
        states={
            admin.WAITING_CHAT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin.process_chat_message)]
        },
        fallbacks=[CallbackQueryHandler(admin.show_admin_panel, pattern="^adm_panel$")]
    )
    app.add_handler(chat_conv)

    # Инициализация промокодов при старте
    async def post_init(application):
        await init_promo_codes()

    app.post_init = post_init

    print("🤠 SYSTEM READY. SALOON IS OPEN.")
    print("📜 Кодекс Салуна активирован для новых пользователей")
    print(f"🔐 Админка: /admin_{ADMIN_SECRET_CODE}")
    app.run_polling()


if __name__ == "__main__":
    main()
