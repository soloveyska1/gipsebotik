import asyncio
import aiosqlite
import json

DB_PATH = "bot_database.db"

DEFAULT_PRICES = {
    'samostoyatelnye': 2000,
    'kursovaya_teoreticheskaya': 8000,
    'kursovaya_s_empirikov': 12000,
    'diplomnaya': 35000,
    'magisterskaya': 35000
}

async def update():
    print("🚀 Начинаем апгрейд до God Mode...")
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Создаем таблицу настроек (для цен)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # Заливаем дефолтные цены, если их нет
        for key, price in DEFAULT_PRICES.items():
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (f"price_{key}", str(price)))

        # 2. Добавляем колонку "Роль" пользователям (admin, manager, user)
        try:
            await db.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
            print("✅ Колонка role добавлена.")
        except Exception:
            print("ℹ️ Колонка role уже есть.")

        # 3. Добавляем колонку "Менеджер" в заказы
        try:
            await db.execute("ALTER TABLE orders ADD COLUMN manager_id INTEGER")
            print("✅ Колонка manager_id добавлена.")
        except Exception:
            print("ℹ️ Колонка manager_id уже есть.")

        await db.commit()
    print("😎 База готова к режиму Бога!")

if __name__ == "__main__":
    asyncio.run(update())