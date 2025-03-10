import logging
import aiofiles
import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from logging.handlers import RotatingFileHandler
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN, ADMIN_IDS, DB_NAME
from database import (
    add_user, get_user_count, get_all_users, add_file, get_file, 
    add_channel, remove_channel, get_channels, is_file_code_exists, 
    remove_file, add_file_request, get_user_requests, get_all_file_codes
)
import pandas as pd
from datetime import datetime, timedelta
import sqlite3
import sys

# Logging sozlamalari
log_file = "bot.log"
max_log_size = 5 * 1024 * 1024  # 5 MB
backup_count = 1
log_format = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        RotatingFileHandler(log_file, maxBytes=max_log_size, backupCount=backup_count, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# UTF-8 kodlashni majburiy qilish
if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

# Bot va Dispatcher ni ishga tushirish
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
storage = MemoryStorage()
dp = Dispatcher(bot=bot, storage=storage)

ADMINS = ADMIN_IDS

# Tugmalar
admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📥 Excelni yuklash")],
        [KeyboardButton(text="📤 Fayl yuklash"), KeyboardButton(text="🗑 Fayl o‘chirish")],
        [KeyboardButton(text="📢 Reklama"), KeyboardButton(text="🔗 Majburiy obuna")],
        [KeyboardButton(text="👤 Foydalanuvchi statistikasi"), KeyboardButton(text="📈 Umumiy statistika")],
        [KeyboardButton(text="📋 Fayl kodlari ro‘yxati")]
    ],
    resize_keyboard=True
)

reklama_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 SMS"), KeyboardButton(text="🖼 Rasm")],
        [KeyboardButton(text="🎥 Video"), KeyboardButton(text="📁 Fayl")],
        [KeyboardButton(text="🎞 GIF"), KeyboardButton(text="🎙 Ovozli xabar")],
        [KeyboardButton(text="📍 Lokatsiya"), KeyboardButton(text="🎵 Musiqa")],
        [KeyboardButton(text="🔙 Orqaga")]
    ],
    resize_keyboard=True
)

majburiy_obuna_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Kanal qo'shish"), KeyboardButton(text="➖ Kanalni olib tashlash")],
        [KeyboardButton(text="📋 Kanallar ro'yxati"), KeyboardButton(text="🔙 Orqaga")]
    ],
    resize_keyboard=True
)

# State guruhlari
class FileUploadStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_file = State()

class UserStatsStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_filter_start = State()
    waiting_for_filter_end = State()

class FileListStates(StatesGroup):
    listing_files = State()

class FileDeleteStates(StatesGroup):
    waiting_for_code = State()

class ReklamaStates(StatesGroup):
    waiting_for_sms = State()
    waiting_for_photo = State()
    waiting_for_video = State()
    waiting_for_file = State()
    waiting_for_gif = State()
    waiting_for_voice = State()
    waiting_for_location = State()
    waiting_for_music = State()

class MajburiyObunaStates(StatesGroup):
    waiting_for_channel_username = State()
    waiting_for_channel_remove = State()

# Obunani tekshirish
async def check_subscription(user_id):
    if user_id in ADMINS:
        return True
    channels = get_channels()
    for channel in channels:
        try:
            chat_member = await bot.get_chat_member(f"@{channel}", user_id)
            if chat_member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            logger.error(f"Obuna tekshiruvida xato: {e}")
            return False
    return True

# Obuna talab qilish
async def prompt_subscription(message):
    channels = get_channels()
    keyboard = InlineKeyboardMarkup(row_width=1)
    for channel in channels:
        keyboard.add(InlineKeyboardButton(text=f"📢 @{channel} ga obuna bo‘ling", url=f"https://t.me/{channel}"))
    keyboard.add(InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subscription"))
    await message.answer(
        "<b>⚠️ Diqqat!</b>\n<i>Botdan foydalanish uchun quyidagi kanallarga obuna bo‘lishingiz kerak:</i>\n👇 Obuna bo‘lib, “Tekshirish” tugmasini bosing!",
        reply_markup=keyboard
    )

# Bekor qilish
@dp.message(Command(commands=["cancel"]), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    if message.from_user.id in ADMINS:
        await state.finish()
        await message.answer("🚫 Bekor qilindi. Siz bosh menyudasiz.", reply_markup=admin_keyboard)
    else:
        await message.answer("Siz admin emassiz.")

# Start buyrug‘i
@dp.message(Command(commands=['start']))
async def start_handler(message: types.Message):
    user = message.from_user
    logger.info(f"Foydalanuvchi {user.id} start bosdi.")
    add_user(user.id, user.first_name, user.last_name, user.username)

    if not await check_subscription(user.id):
        await prompt_subscription(message)
        return

    if user.id in ADMINS:
        await message.answer(
            f"<b>👨‍💻 Admin Panelga Xush Kelibsiz, {user.first_name}!</b>\n<i>Assalomu alaykum, hurmatli admin!</i>\n🔧 Botni boshqarish uchun quyidagi imkoniyatlardan foydalaning:\n📊 <u>Statistika</u> | 📤 <u>Fayl yuklash</u> | 📢 <u>Reklama</u>\n👇 Tugmalarni sinab ko‘ring!",
            reply_markup=admin_keyboard
        )
    else:
        await message.answer(
            "<b>🎉 Botga Xush Kelibsiz!</b>\n🌟 <i>Fayllarni tez va oson yuklab oling!</i>\n🇺🇿 <b>Salom!</b> Fayl olish uchun kodni kiriting\n🇷🇺 <b>Привет!</b> Введите код файла\n👉 Misol: <code>12345</code>\nℹ️ Yordam uchun: /help"
        )

# Help buyrug‘i
@dp.message(Command(commands=['help']))
async def help_handler(message: types.Message):
    if not await check_subscription(message.from_user.id):
        await prompt_subscription(message)
        return
    await message.answer("ℹ️ Botdan foydalanish:\n1. Fayl olish uchun raqamli kodni kiriting.\n2. Fayl Kodlarni, faqat https://t.me/chorniy_staylle da topish mumkin   \n3. Agar savolingiz bo‘lsa, Dasturchi bilan bog‘laning.\n3. Bot dasturchisi @Ifrs_7")

# Obuna tekshiruvi callback
@dp.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription_callback(callback: types.CallbackQuery):
    messages = {
        "uz": "❌ Hali barcha kanallarga obuna bo‘lmagansiz.",
        "ru": "❌ Вы еще не подписались на все каналы."
    }
    if await check_subscription(callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer("✅ Obuna tekshirildi! Fayl kodini kiriting:")
    else:
        user_lang = callback.from_user.language_code or "uz"
        warning_message = messages.get(user_lang, messages["uz"])
        await callback.answer(warning_message, show_alert=True)

# Fayl yuborish
async def send_file_by_type(chat_id, file_id, file_type, caption):
    methods = {
        "document": bot.send_document,
        "photo": bot.send_photo,
        "video": bot.send_video,
        "audio": bot.send_audio,
        "animation": bot.send_animation,
        "voice": bot.send_voice,
        "sticker": bot.send_sticker
    }
    if file_type in methods:
        await methods[file_type](chat_id, file_id, caption=caption)
    else:
        await bot.send_message(chat_id, "❌ Noto‘g‘ri fayl turi!")

@dp.message(lambda message: message.text.isdigit())
async def get_file_by_code(message: types.Message):
    user_id = message.from_user.id
    if not await check_subscription(user_id):
        await prompt_subscription(message)
        return

    file_code = message.text.strip()
    file_data = get_file(file_code)
    
    if file_data:
        add_file_request(user_id, file_code)
    
    if file_data:
        file_id, file_link, file_type, caption = file_data
        if file_id:
            await send_file_by_type(message.chat.id, file_id, file_type, caption or f"📥 '{file_code}' kodi uchun fayl")
        elif file_link:
            await message.answer(f"📥 '{file_code}' kodi uchun havola:\n{file_link}")
        else:
            await message.answer("❌ Fayl topilmadi yoki noto‘g‘ri formatda saqlangan.")
    else:
        await message.answer("❌ Bunday kod bilan fayl topilmadi.")

@dp.message(lambda message: message.text == "📈 Umumiy statistika")
async def export_all_users_stats(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, first_name, last_name, username, created_at FROM users")
            users = cursor.fetchall()
            cursor.execute("SELECT user_id, COUNT(*) FROM file_requests GROUP BY user_id")
            request_counts = dict(cursor.fetchall())
        
        data = {
            "Foydalanuvchi ID": [], "Ism": [], "Username": [],
            "Ro‘yxatdan o‘tgan": [], "So‘rovlar soni": []
        }
        for user in users:
            user_id, first_name, last_name, username, created_at = user
            data["Foydalanuvchi ID"].append(user_id)
            data["Ism"].append(f"{first_name} {last_name or ''}")
            data["Username"].append(f"@{username or 'Yo‘q'}")
            data["Ro‘yxatdan o‘tgan"].append(created_at)
            data["So‘rovlar soni"].append(request_counts.get(user_id, 0))
        
        df = pd.DataFrame(data)
        file_name = "all_users_stats.xlsx"
        df.to_excel(file_name, index=False)
        
        with open(file_name, "rb") as file:
            await message.answer_document(types.InputFile(file), caption="📈 Barcha foydalanuvchilar statistikasi")
        os.remove(file_name)
    except Exception as e:
        logger.error(f"Umumiy statistika eksportida xatolik: {e}")
        await message.answer("❌ Statistika eksport qilishda xatolik yuz berdi!")

@dp.message(lambda message: message.text == "📊 Statistika")
async def show_stats(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    user_count = get_user_count()
    await message.answer(f"📊 Botdagi umumiy foydalanuvchilar soni: {user_count} ta")

@dp.message(lambda message: message.text == "📥 Excelni yuklash")
async def download_excel(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    users = get_all_users()
    df = pd.DataFrame(users, columns=["ID", "Telegram ID", "Ism", "Familiya", "Username", "Ro‘yxatdan o‘tgan vaqt"])
    df.to_excel("users.xlsx", index=False)
    with open("users.xlsx", "rb") as file:
        await message.answer_document(types.InputFile(file), caption="📥 Foydalanuvchilar ro‘yxati (Excel)")
    os.remove("users.xlsx")

@dp.message(lambda message: message.text == "📤 Fayl yuklash")
async def request_file_code(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("📥 Fayl kodini kiriting (faqat raqam) yoki bekor qilish uchun /cancel bosing:")
    await FileUploadStates.waiting_for_code.set()

def parse_date_input(user_input):
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    user_input = user_input.lower().strip()
    
    if user_input == "bugun":
        return today_start.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d %H:%M:%S")
    elif user_input == "kecha":
        yesterday_start = today_start - timedelta(days=1)
        yesterday_end = today_start - timedelta(seconds=1)
        return yesterday_start.strftime("%Y-%m-%d %H:%M:%S"), yesterday_end.strftime("%Y-%m-%d %H:%M:%S")
    elif user_input == "hafta":
        week_start = today_start - timedelta(days=7)
        return week_start.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d %H:%M:%S")
    elif user_input == "barchasi":
        return None, None
    else:
        try:
            datetime.strptime(user_input, "%Y-%m-%d %H:%M:%S")
            return user_input, user_input
        except ValueError:
            return None, None

@dp.message(lambda message: message.text == "👤 Foydalanuvchi statistikasi")
async def request_user_stats(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("👤 Statistikasini ko‘rish uchun foydalanuvchi ID’sini kiriting yoki /cancel bosing:")
    await UserStatsStates.waiting_for_user_id.set()

@dp.message(state=UserStatsStates.waiting_for_user_id)
async def process_user_stats(message: types.Message, state: FSMContext):
    user_id = message.text.strip()
    if not user_id.isdigit():
        await message.answer("❌ Noto‘g‘ri format! Iltimos, faqat raqamli ID kiriting.")
        return
    
    user_id = int(user_id)
    await state.update_data(user_id=user_id)
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT first_name, last_name, username, created_at FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        if not user_data:
            await message.answer(f"❌ ID: {user_id} bilan foydalanuvchi topilmadi!", reply_markup=admin_keyboard)
            await state.finish()
            return
    
    await message.answer(
        "📅 So‘rovlar uchun boshlanish vaqtini kiriting (YYYY-MM-DD HH:MM:SS formatida, masalan, 2025-03-10 00:00:00) yoki 'barchasi' deb yozing\n yoki /cancel bosing:"
    )
    await UserStatsStates.waiting_for_filter_start.set()

@dp.message(state=UserStatsStates.waiting_for_filter_start)
async def process_filter_start(message: types.Message, state: FSMContext):
    start_input = message.text.strip()
    data = await state.get_data()
    user_id = data["user_id"]
    
    start_date, _ = parse_date_input(start_input)
    if start_date is None and start_input.lower() != "barchasi":
        await message.answer("❌ Noto‘g‘ri format! 'bugun', 'kecha', 'hafta', 'barchasi' yoki YYYY-MM-DD HH:MM:SS kiriting\n yoki /cancel bosing:")
        return
    
    await state.update_data(start_date=start_date)
    await message.answer(
        "📅 So‘rovlar uchun tugash vaqtini kiriting ('bugun', 'kecha', 'hafta', 'barchasi' yoki YYYY-MM-DD HH:MM:SS)\n yoki /cancel bosing:"
    )
    await UserStatsStates.waiting_for_filter_end.set()

@dp.message(state=UserStatsStates.waiting_for_filter_end)
async def process_filter_end(message: types.Message, state: FSMContext):
    end_input = message.text.strip()
    data = await state.get_data()
    user_id = data["user_id"]
    start_date = data["start_date"]
    
    _, end_date = parse_date_input(end_input)
    if end_date is None and end_input.lower() != "barchasi":
        await message.answer("❌ Noto‘g‘ri format! 'bugun', 'kecha', 'hafta', 'barchasi' yoki YYYY-MM-DD HH:MM:SS kiriting\n yoki /cancel bosing:")
        return
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT first_name, last_name, username, created_at FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        if not user_data:
            await message.answer(f"❌ ID: {user_id} bilan foydalanuvchi topilmadi!", reply_markup=admin_keyboard)
            await state.finish()
            return
        first_name, last_name, username, created_at = user_data
        requests = get_user_requests(user_id, start_date, end_date)
        request_count = len(requests)
    
    response = (
        f"👤 Foydalanuvchi statistikasi:\n"
        f"ID: {user_id}\n"
        f"Ism: {first_name} {last_name or ''}\n"
        f"Username: @{username or 'Yo‘q'}\n"
        f"Ro‘yxatdan o‘tgan: {created_at}\n"
        f"So‘rovlar soni: {request_count}\n"
    )
    if requests:
        response += "So‘nggi so‘rovlar:\n" + "\n".join([f"- Kod: {req[0]}, Vaqt: {req[1]}" for req in requests[:5]])
    else:
        response += "So‘rovlar: Yo‘q"

    export_keyboard = InlineKeyboardMarkup()
    export_keyboard.add(InlineKeyboardButton("📥 Excel sifatida yuklash", callback_data=f"export_stats_{user_id}_{start_date or 'all'}_{end_date or 'all'}"))
    await message.answer(response, reply_markup=export_keyboard)
    await state.finish()

@dp.callback_query(lambda c: c.data.startswith("export_stats_"))
async def export_user_stats(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    user_id = int(parts[2])
    start_date = parts[3] if parts[3] != "all" else None
    end_date = parts[4] if parts[4] != "all" else None
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT first_name, last_name, username, created_at FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        if not user_data:
            await callback.message.answer("❌ Foydalanuvchi topilmadi!")
            return
        first_name, last_name, username, created_at = user_data
        requests = get_user_requests(user_id, start_date, end_date)
    
    data = {
        "Foydalanuvchi ID": [user_id],
        "Ism": [f"{first_name} {last_name or ''}"],
        "Username": [f"@{username or 'Yo‘q'}"],
        "Ro‘yxatdan o‘tgan": [created_at],
        "So‘rovlar soni": [len(requests)]
    }
    if requests:
        data["So‘rov kodi"] = [req[0] for req in requests]
        data["So‘rov vaqti"] = [req[1] for req in requests]
    df = pd.DataFrame(data)
    file_name = f"user_stats_{user_id}.xlsx"
    df.to_excel(file_name, index=False)
    
    with open(file_name, "rb") as file:
        await callback.message.answer_document(types.InputFile(file), caption=f"📊 Foydalanuvchi {user_id} statistikasi (Filtr: {start_date or 'barchasi'} - {end_date or 'barchasi'})")
    os.remove(file_name)
    await callback.answer()

FILE_TYPES = ["document", "photo", "video", "audio", "animation", "voice", "sticker"]
ITEMS_PER_PAGE = 10

@dp.message(lambda message: message.text == "📋 Fayl kodlari ro‘yxati")
async def list_file_codes(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("<b>🚫 Xatolik!</b>\n<i>Siz admin emassiz. Bu funksiya faqat adminlar uchun!</i>")
        return
    
    file_type_emojis = {
        "all": "📦", "document": "📄", "photo": "🖼️", "video": "🎥",
        "audio": "🎵", "animation": "🎞️", "voice": "🎤", "sticker": "💟"
    }
    filter_keyboard = InlineKeyboardMarkup(row_width=2)
    filter_keyboard.add(
        InlineKeyboardButton(f"{file_type_emojis['all']} Barchasi", callback_data="filter_all"),
        *[InlineKeyboardButton(f"{file_type_emojis[ftype]} {ftype.capitalize()}", callback_data=f"filter_{ftype}") for ftype in FILE_TYPES]
    )
    await message.answer(
        "<b>📋 Fayl Kodlari Ro‘yxati</b>\n<i>Fayllarni ko‘rish uchun quyidagi filtrlarlardan birini tanlang:</i>\n👇 Turini tanlang!",
        reply_markup=filter_keyboard
    )

@dp.callback_query(lambda c: c.data.startswith("filter_"))
async def process_file_filter(callback: types.CallbackQuery, state: FSMContext):
    filter_type = callback.data.split("_")[1]
    file_type = None if filter_type == "all" else filter_type
    
    file_codes = get_all_file_codes(file_type=file_type)
    if not file_codes:
        await callback.message.delete()
        await callback.message.answer(
            "<b>🚫 Hech narsa topilmadi!</b>\n<i>Tanlangan turda hali fayl kodlari mavjud emas.</i>\n📤 Yangi fayl qo‘shish uchun <b>“Fayl yuklash”</b>ni sinab ko‘ring!",
            reply_markup=admin_keyboard
        )
        await callback.answer()
        return
    
    await state.update_data(file_codes=file_codes, file_type=file_type, current_page=0)
    await show_file_page(callback.message, state, 0)
    await FileListStates.listing_files.set()
    await callback.answer()

async def show_file_page(message: types.Message, state: FSMContext, page: int):
    data = await state.get_data()
    file_codes = data["file_codes"]
    file_type = data["file_type"]
    
    total_items = len(file_codes)
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    if page < 0 or page >= total_pages:
        return
    
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, total_items)
    page_items = file_codes[start_idx:end_idx]
    
    response = (
        f"<b>📋 Fayl Kodlari Ro‘yxati</b> (<u>{'Barchasi' if not file_type else file_type.capitalize()}</u>)\n"
        "<i>Quyida mavjud fayllar ro‘yxati keltirilgan:</i>\n\n"
    )
    for code, f_type, uploaded_at, caption in page_items:
        caption_text = f" - <i>{caption}</i>" if caption else ""
        response += (
            f"🔹 <b>Kod:</b> <code>{code}</code> | <b>Tur:</b> {f_type} | "
            f"<b>Yuklangan:</b> {uploaded_at}{caption_text}\n"
        )
    
    response += f"\nSahifa: {page + 1}/{total_pages}"
    
    nav_keyboard = InlineKeyboardMarkup()
    if page > 0:
        nav_keyboard.add(InlineKeyboardButton("⏪ Oldingi", callback_data=f"page_{page-1}"))
    if page < total_pages - 1:
        nav_keyboard.insert(InlineKeyboardButton("Keyingi ⏩", callback_data=f"page_{page+1}"))
    nav_keyboard.add(InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu"))
    
    await message.edit_text(response, reply_markup=nav_keyboard)

@dp.callback_query(lambda c: c.data.startswith("page_"), state=FileListStates.listing_files)
async def process_page_navigation(callback: types.CallbackQuery, state: FSMContext):
    page = int(callback.data.split("_")[1])
    await show_file_page(callback.message, state, page)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_to_menu", state=FileListStates.listing_files)
async def back_to_admin_menu_from_list(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await callback.message.answer("👨‍💻 Admin panelga xush kelibsiz!", reply_markup=admin_keyboard)
    await callback.message.delete()
    await callback.answer()

@dp.message(lambda message: message.text == "🗑 Fayl o‘chirish")
async def request_file_delete_code(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("🗑 O‘chirish uchun fayl kodini kiriting yoki bekor qilish uchun /cancel bosing:")
    await FileDeleteStates.waiting_for_code.set()

@dp.message(state=FileDeleteStates.waiting_for_code)
async def process_file_delete(message: types.Message, state: FSMContext):
    file_code = message.text.strip()
    if not file_code.isdigit():
        await message.answer("❌ Noto‘g‘ri format! Iltimos, faqat raqam kiriting.")
        return
    
    success = remove_file(file_code)
    if success:
        await message.answer(f"✅ '{file_code}' kodli fayl o‘chirildi!", reply_markup=admin_keyboard)
    else:
        await message.answer(f"❌ '{file_code}' kodli fayl topilmadi!", reply_markup=admin_keyboard)
    await state.finish()

@dp.message(state=FileUploadStates.waiting_for_code)
async def receive_file_code(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Noto‘g‘ri format! Iltimos, faqat raqam kiriting.")
        return

    file_code = message.text.strip()
    if is_file_code_exists(file_code):
        await message.answer(f"❌ {file_code} kodi allaqachon mavjud! Iltimos, boshqa kod kiriting\nyoki bekor qilish uchun /cancel bosing: ")
        return
    
    await state.update_data(file_code=file_code)
    await message.answer("📤 Endi faylni yuboring yoki bekor qilish uchun /cancel bosing:")
    await FileUploadStates.waiting_for_file.set()

@dp.message(content_types=['document', 'photo', 'video', 'audio', 'animation', 'voice', 'sticker'], state=FileUploadStates.waiting_for_file)
async def receive_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    file_code = data.get("file_code")
    
    file_types = {
        "document": message.document,
        "photo": message.photo[-1] if message.photo else None,
        "video": message.video,
        "audio": message.audio,
        "animation": message.animation,
        "voice": message.voice,
        "sticker": message.sticker
    }
    
    for f_type, f_obj in file_types.items():
        if f_obj:
            file_id = f_obj.file_id
            file_type = f_type
            break
    else:
        await message.answer("❌ Noto'g'ri format! Iltimos, faylni yuboring.")
        return
    
    caption = message.caption if message.caption else None
    success = add_file(file_code, file_id=file_id, file_type=file_type, caption=caption)
    
    if success:
        await message.answer(f"✅ Fayl '{file_code}' kodi bilan saqlandi.", reply_markup=admin_keyboard)
    else:
        await message.answer("❌ Fayl saqlashda xatolik yuz berdi!")
    
    await state.finish()

@dp.message(state=FileUploadStates.waiting_for_file)
async def handle_wrong_input_file(message: types.Message):
    await message.answer("❌ Noto'g'ri format! Iltimos, faylni yuboring yoki /cancel bosing:")

# Reklama funksiyalari
async def send_to_all(users, method, *args, content_type="unknown", **kwargs):
    semaphore = asyncio.Semaphore(20)
    batch_size = 1000

    async def send_message_with_semaphore(user):
        async with semaphore:
            try:
                await method(user[1], *args, **kwargs)
            except Exception as e:
                if "bot was blocked by the user" in str(e):
                    logger.warning(f"Foydalanuvchi botni bloklagan: {user[1]}")
                else:
                    logger.error(f"Reklama yuborishda xatolik ({content_type}): {user[1]} - {e}")
            await asyncio.sleep(0.05)

    for i in range(0, len(users), batch_size):
        batch = users[i:i + batch_size]
        tasks = [send_message_with_semaphore(user) for user in batch]
        await asyncio.gather(*tasks)
        await asyncio.sleep(1)

@dp.message(lambda message: message.text == "📢 Reklama")
async def reklama_menu(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("Reklama turini tanlang:", reply_markup=reklama_keyboard)

@dp.message(lambda message: message.text == "🔙 Orqaga", state='*')
async def back_to_admin_menu(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await state.finish()
    await message.answer("Admin panelga qaytdingiz.", reply_markup=admin_keyboard)

@dp.message(lambda message: message.text == "📝 SMS")
async def request_sms_reklama(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("Reklama matnini kiriting yoki bekor qilish uchun /cancel bosing:")
    await ReklamaStates.waiting_for_sms.set()

@dp.message(content_types=['text'], state=ReklamaStates.waiting_for_sms)
async def send_sms_reklama(message: types.Message, state: FSMContext):
    reklama_text = message.text
    users = get_all_users()
    await send_to_all(users, bot.send_message, reklama_text)
    await message.answer("✅ SMS reklama barcha foydalanuvchilarga yuborildi!", reply_markup=admin_keyboard)
    await state.finish()

@dp.message(content_types=['any'], state=ReklamaStates.waiting_for_sms)
async def handle_wrong_input_sms(message: types.Message):
    await message.answer("❌ Faqat matn yuboring!")

@dp.message(lambda message: message.text == "🖼 Rasm")
async def request_photo_reklama(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("Rasmni yuboring (jpg/png) yoki bekor qilish uchun /cancel bosing:")
    await ReklamaStates.waiting_for_photo.set()

@dp.message(content_types=['photo', 'document'], state=ReklamaStates.waiting_for_photo)
async def send_photo_reklama(message: types.Message, state: FSMContext):
    users = get_all_users()
    caption = message.caption if message.caption else ""
    
    if message.photo:
        photo_id = message.photo[-1].file_id
        await send_to_all(users, bot.send_photo, photo_id, content_type="photo", caption=caption)
        await message.answer("✅ Rasm reklama barcha foydalanuvchilarga yuborildi!", reply_markup=admin_keyboard)
    elif message.document:
        file_name = message.document.file_name.lower()
        if file_name.endswith(('.jpg', '.png')):
            file_info = await bot.get_file(message.document.file_id)
            file_path = file_info.file_path
            downloaded_file = await bot.download_file(file_path)
            file_bytes = downloaded_file.read()
            temp_file_name = f"temp_{message.document.file_id}.{file_name.split('.')[-1]}"
            async with aiofiles.open(temp_file_name, 'wb') as f:
                await f.write(file_bytes)
            with open(temp_file_name, 'rb') as photo:
                await send_to_all(users, bot.send_photo, types.InputFile(photo), content_type="photo_document", caption=caption)
            os.remove(temp_file_name)
            await message.answer("✅ Rasm reklama barcha foydalanuvchilarga yuborildi!", reply_markup=admin_keyboard)
        else:
            await message.answer("❌ Faqat .jpg yoki .png formatdagi fayllar qabul qilinadi!")
            return
    await state.finish()

@dp.message(content_types=['any'], state=ReklamaStates.waiting_for_photo)
async def handle_wrong_input_photo(message: types.Message):
    await message.answer("❌ Faqat rasm (jpg/png) yuboring!")

@dp.message(lambda message: message.text == "🎥 Video")
async def request_video_reklama(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("Videoni yuboring yoki bekor qilish uchun /cancel bosing:")
    await ReklamaStates.waiting_for_video.set()

@dp.message(content_types=['video'], state=ReklamaStates.waiting_for_video)
async def send_video_reklama(message: types.Message, state: FSMContext):
    video_id = message.video.file_id
    caption = message.caption if message.caption else ""
    users = get_all_users()
    await send_to_all(users, bot.send_video, video_id, content_type="video", caption=caption)
    await message.answer("✅ Video reklama barcha foydalanuvchilarga yuborildi!", reply_markup=admin_keyboard)
    await state.finish()

@dp.message(content_types=['any'], state=ReklamaStates.waiting_for_video)
async def handle_wrong_input_video(message: types.Message):
    await message.answer("❌ Faqat video yuboring!")

@dp.message(lambda message: message.text == "📁 Fayl")
async def request_file_reklama(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("Faylni yuboring yoki bekor qilish uchun /cancel bosing:")
    await ReklamaStates.waiting_for_file.set()

@dp.message(content_types=['document'], state=ReklamaStates.waiting_for_file)
async def send_file_reklama(message: types.Message, state: FSMContext):
    document_id = message.document.file_id
    caption = message.caption if message.caption else ""
    users = get_all_users()
    await send_to_all(users, bot.send_document, document_id, caption=caption)
    await message.answer("✅ Fayl reklama barcha foydalanuvchilarga yuborildi!", reply_markup=admin_keyboard)
    await state.finish()

@dp.message(content_types=['any'], state=ReklamaStates.waiting_for_file)
async def handle_wrong_input_file(message: types.Message):
    await message.answer("❌ Faqat fayl (dokument) yuboring!")

@dp.message(lambda message: message.text == "🎞 GIF")
async def request_gif_reklama(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("GIFni yuboring yoki bekor qilish uchun /cancel bosing:")
    await ReklamaStates.waiting_for_gif.set()

@dp.message(content_types=['animation'], state=ReklamaStates.waiting_for_gif)
async def send_gif_reklama(message: types.Message, state: FSMContext):
    gif_id = message.animation.file_id
    caption = message.caption if message.caption else ""
    users = get_all_users()
    await send_to_all(users, bot.send_animation, gif_id, caption=caption)
    await message.answer("✅ GIF reklama barcha foydalanuvchilarga yuborildi!", reply_markup=admin_keyboard)
    await state.finish()

@dp.message(content_types=['any'], state=ReklamaStates.waiting_for_gif)
async def handle_wrong_input_gif(message: types.Message):
    await message.answer("❌ Faqat GIF yuboring!")

@dp.message(lambda message: message.text == "🎙 Ovozli xabar")
async def request_voice_reklama(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("Ovozli xabarni yuboring yoki bekor qilish uchun /cancel bosing:")
    await ReklamaStates.waiting_for_voice.set()

@dp.message(content_types=['voice'], state=ReklamaStates.waiting_for_voice)
async def send_voice_reklama(message: types.Message, state: FSMContext):
    voice_id = message.voice.file_id
    users = get_all_users()
    await send_to_all(users, bot.send_voice, voice_id)
    await message.answer("✅ Ovozli xabar reklama barcha foydalanuvchilarga yuborildi!", reply_markup=admin_keyboard)
    await state.finish()

@dp.message(content_types=['any'], state=ReklamaStates.waiting_for_voice)
async def handle_wrong_input_voice(message: types.Message):
    await message.answer("❌ Faqat ovozli xabar yuboring!")

@dp.message(lambda message: message.text == "📍 Lokatsiya")
async def request_location_reklama(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("Lokatsiyani yuboring yoki bekor qilish uchun /cancel bosing:")
    await ReklamaStates.waiting_for_location.set()

@dp.message(content_types=['location'], state=ReklamaStates.waiting_for_location)
async def send_location_reklama(message: types.Message, state: FSMContext):
    location = message.location
    users = get_all_users()
    await send_to_all(users, bot.send_location, location.latitude, location.longitude)
    await message.answer("✅ Lokatsiya reklama barcha foydalanuvchilarga yuborildi!", reply_markup=admin_keyboard)
    await state.finish()

@dp.message(content_types=['any'], state=ReklamaStates.waiting_for_location)
async def handle_wrong_input_location(message: types.Message):
    await message.answer("❌ Faqat lokatsiya yuboring!")

@dp.message(lambda message: message.text == "🎵 Musiqa")
async def request_music_reklama(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("Musiqani yuboring (mp3/m4a) yoki bekor qilish uchun /cancel bosing:")
    await ReklamaStates.waiting_for_music.set()

@dp.message(content_types=['audio'], state=ReklamaStates.waiting_for_music)
async def send_music_reklama(message: types.Message, state: FSMContext):
    audio_id = message.audio.file_id
    caption = message.caption if message.caption else ""
    users = get_all_users()
    await send_to_all(users, bot.send_audio, audio_id, caption=caption)
    await message.answer("✅ Musiqa reklama barcha foydalanuvchilarga yuborildi!", reply_markup=admin_keyboard)
    await state.finish()

@dp.message(content_types=['any'], state=ReklamaStates.waiting_for_music)
async def handle_wrong_input_music(message: types.Message):
    await message.answer("❌ Faqat musiqa (audio) yuboring!")

@dp.message(lambda message: message.text == "🔗 Majburiy obuna")
async def majburiy_obuna_menu(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("Majburiy obuna sozlamalari:", reply_markup=majburiy_obuna_keyboard)

@dp.message(lambda message: message.text == "➕ Kanal qo'shish")
async def add_channel_handler(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("Kanal username ni @ belgisi bilan kiriting (masalan, @channel_username)\nYoki bekor qilish uchun /cancel bosing:")
    await MajburiyObunaStates.waiting_for_channel_username.set()

@dp.message(state=MajburiyObunaStates.waiting_for_channel_username)
async def process_add_channel(message: types.Message, state: FSMContext):
    channel_username = message.text.strip()
    if not channel_username.startswith("@"):
        await message.answer("❌ Noto'g'ri format! Iltimos, @ belgisi bilan kiriting\nYoki bekor qilish uchun /cancel bosing:")
        return
    
    success = add_channel(channel_username)
    if success:
        await message.answer(f"✅ {channel_username} kanali qo'shildi!", reply_markup=admin_keyboard)
    else:
        await message.answer(f"❌ {channel_username} kanali allaqachon mavjud!", reply_markup=admin_keyboard)
    await state.finish()

@dp.message(lambda message: message.text == "➖ Kanalni olib tashlash")
async def remove_channel_handler(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("Olib tashlash uchun kanal username ni kiriting (masalan, @channel_username)\nYoki bekor qilish uchun /cancel bosing:")
    await MajburiyObunaStates.waiting_for_channel_remove.set()

@dp.message(state=MajburiyObunaStates.waiting_for_channel_remove)
async def process_remove_channel(message: types.Message, state: FSMContext):
    channel_username = message.text.strip().lstrip('@')
    success = remove_channel(channel_username)
    if success:
        await message.answer(f"✅ @{channel_username} kanali olib tashlandi!", reply_markup=admin_keyboard)
    else:
        await message.answer(f"❌ @{channel_username} kanali topilmadi!", reply_markup=admin_keyboard)
    await state.finish()

@dp.message(lambda message: message.text == "📋 Kanallar ro'yxati")
async def list_channels_handler(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    channels = get_channels()
    if channels:
        response = "📋 Majburiy obuna kanallari:\n" + "\n".join([f"👉 @{ch}" for ch in channels])
    else:
        response = "❌ Hech qanday kanal qo'shilmagan"
    await message.answer(response, reply_markup=admin_keyboard)

@dp.message()
async def handle_unknown_input(message: types.Message):
    if not await check_subscription(message.from_user.id):
        await prompt_subscription(message)
    else:
        await message.answer("❌ Faqat raqamli kod kiritishingiz mumkin!")

if __name__ == "__main__":
    try:
        logger.info("Bot ishga tushmoqda...")
        dp.run_polling(allowed_updates=["message", "callback_query"])
    except Exception as e:
        logger.error(f"Bot ishga tushishda xatolik: {e}")
