from dotenv import load_dotenv
import os

# .env faylidan o'zgaruvchilarni yuklash
load_dotenv()

# Kalitlarni aniqlash
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DB_NAME = os.getenv("DB_NAME", "database.db")  # Default qiymat bilan
API_KEY = os.getenv("API_KEY", "")  # Ixtiyoriy, agar ishlatilsa

# Tekshirish uchun log
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN .env faylida topilmadi!")
