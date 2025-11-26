import logging
import os
import asyncio
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)

# Импорты конфига и базы
from config import BOT_TOKEN, LOGS_DIR
from database.core import init_db, create_promo_code

# Импорты хендлеров
from handlers import client

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

    # Инициализация промокодов при старте
    async def post_init(application):
        await init_promo_codes()

    app.post_init = post_init

    print("🤠 SYSTEM READY. SALOON IS OPEN.")
    print("📜 Кодекс Салуна активирован для новых пользователей")
    app.run_polling()


if __name__ == "__main__":
    main()
