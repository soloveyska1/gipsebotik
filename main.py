"""
🤖 GIPSEBOT - Telegram Bot for Student Services
Главный файл запуска
"""
import logging
import os
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)

# Импорты конфига и базы
from config import BOT_TOKEN, LOGS_DIR
from database.core import init_db

# Импорты хендлеров
from handlers import client, order_flow, admin, chat
from handlers.error_handler import error_handler

# Импорт дашборда (мониторинг в канал)
from services.dashboard import LiveDashboard

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

def main():
    print("🔌 Подключаем базу данных...")
    init_db()
    
    print("🚀 Инициализация бота...")
    app = Application.builder().token(BOT_TOKEN).build()

    # === ЗАПУСК ДАШБОРДА ===
    # Будет обновлять статус бота в канале логов раз в минуту
    dashboard = LiveDashboard()
    dashboard.attach(app)
    print("📊 Live Dashboard подключен.")

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
        fallbacks=[CallbackQueryHandler(client.profile, pattern="^open_profile$")]
    )
    app.add_handler(promo_conv)

    # Прайс-лист
    app.add_handler(CallbackQueryHandler(client.show_price_list, pattern="^price_list$"))
    app.add_handler(CallbackQueryHandler(client.show_price_card, pattern="^price_srv_"))

    # Кодекс чести
    app.add_handler(CallbackQueryHandler(client.show_code_of_honor, pattern="^code_honor$"))
    app.add_handler(CallbackQueryHandler(client.accept_rules, pattern="^rules_accept$"))

    # === ОТЗЫВЫ ===
    review_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(client.ask_review, pattern="^write_review$")],
        states={
            client.REVIEW_STATE: [MessageHandler(filters.TEXT | filters.PHOTO, client.submit_review)]
        },
        fallbacks=[CallbackQueryHandler(client.cancel_review, pattern="^open_profile$")]
    )
    app.add_handler(review_conv)

    # === ОФОРМЛЕНИЕ ЗАКАЗА (С ИСПРАВЛЕНИЕМ ЗАВИСАНИЯ) ===
    order_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(order_flow.start_order, pattern="^order_start$")],
        states={
            # Шаг 1: Выбор типа
            order_flow.TYPE: [CallbackQueryHandler(order_flow.get_type, pattern="^srv_")],
            
            # Шаг 2: Ввод темы (ИСПРАВЛЕНО)
            order_flow.TOPIC: [
                # Ловим файлы, фото, ГОЛОСОВЫЕ и текст
                MessageHandler(
                    filters.Document.ALL | filters.PHOTO | filters.VOICE | filters.TEXT & ~filters.COMMAND, 
                    order_flow.get_topic
                ),
                # Ловим кнопки "Помощь" и "Назад" (правильные паттерны)
                CallbackQueryHandler(order_flow.get_topic, pattern="^topic_help$|^srv_back$")
            ],

            # Шаг 3: Дедлайн
            order_flow.DEADLINE: [CallbackQueryHandler(order_flow.get_deadline, pattern="^time_|^back_to_topic$")],
            
            # Шаг 4: Допы (Upsell)
            order_flow.UPSELL: [CallbackQueryHandler(order_flow.get_upsell, pattern="^toggle_|^upsell_done$|^back_to_deadline$")],
            
            # Шаг 5: Выбор оплаты
            order_flow.PAY_CHOICE: [CallbackQueryHandler(order_flow.handle_payment_choice, pattern="^pay_")],
            
            # Шаг 6: Ввод своей суммы
            order_flow.PAY_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_flow.custom_points_input)],
            
            # Шаг 7: Подтверждение
            order_flow.CONFIRM: [CallbackQueryHandler(order_flow.confirm_order, pattern="^submit_order$|^order_start$")]
        },
        fallbacks=[
            CallbackQueryHandler(client.start, pattern="^home$"),
            CallbackQueryHandler(order_flow.start_order, pattern="^order_start$")
        ]
    )
    app.add_handler(order_conv)

    # === АДМИНКА (НОВАЯ CRM) ===
    # Подключаем полный функционал админки
    admin.setup(app)

    # === ЧАТ (МЕНЕДЖЕР <-> КЛИЕНТ) ===
    chat_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(chat.chat_start, pattern="^adm_chat_|^chat_order_")],
        states={
            chat.CHAT_STEP: [
                MessageHandler(filters.ALL & ~filters.COMMAND, chat.chat_process),
                CallbackQueryHandler(chat.chat_start, pattern="^adm_chat_|^chat_order_")
            ]
        },
        fallbacks=[CallbackQueryHandler(chat.cancel_chat, pattern="^chat_close$|^adm_orders_list$|^my_order_")]
    )
    app.add_handler(chat_conv)
    
    # Обработчик ошибок
    app.add_error_handler(error_handler)
    
    # "Пасхалка" на слово "спасибо"
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, client.handle_thanks))

    print("🤠 SYSTEM READY. SALOON IS OPEN.")
    app.run_polling()

if __name__ == "__main__":
    main()