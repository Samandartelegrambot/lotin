import logging
from logging.handlers import RotatingFileHandler
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import TOKEN, ADMINS
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command
from database import add_user, get_user_count, get_all_users, add_file, get_file, add_channel,  remove_channel, get_channels, is_file_code_exists
import pandas as pd
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())


log_file = "bot.log"
max_log_size = 5 * 1024 * 1024  # 5 MB
backup_count = 1  # Faqat 1 ta eski log faylini saqlash

# Log formati
log_format = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        RotatingFileHandler(log_file, maxBytes=max_log_size, backupCount=backup_count),
        logging.StreamHandler()  # Konsolga ham chiqarish
    ]
)

logger = logging.getLogger(__name__)




async def check_subscription(user_id):
    """Foydalanuvchi barcha majburiy kanallarga obuna bo'lganini tekshiradi"""
    if user_id in ADMINS:
        return True
    
    channels = get_channels()  # Bazadagi barcha kanallarni olish
    
    for channel in channels:
        try:
            chat_member = await bot.get_chat_member(f"@{channel}", user_id)
            if chat_member.status not in [types.ChatMemberStatus.MEMBER, 
                                         types.ChatMemberStatus.ADMINISTRATOR, 
                                         types.ChatMemberStatus.CREATOR]:
                return False
        except Exception as e:
            logging.error(f"Error checking subscription for user {user_id} in channel @{channel}: {e}")
            return False
    
    return True


# 📌 Admin tugmalari
admin_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
admin_keyboard.add(
    KeyboardButton("📊 Statistika"),
    KeyboardButton("📥 Excelni yuklash"),
    KeyboardButton("📤 Fayl yuklash"),
    KeyboardButton("📢 Reklama"),
    KeyboardButton("🔗 Majburiy obuna")
)

# Reklama tugmalari
reklama_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
reklama_keyboard.add(
    KeyboardButton("📝 SMS"),
    KeyboardButton("🖼 Rasm"),
    KeyboardButton("🎥 Video"),
    KeyboardButton("📁 Fayl"),
    KeyboardButton("🎞 GIF"),
    KeyboardButton("🎙 Ovozli xabar"),
    KeyboardButton("📍 Lokatsiya"),
    KeyboardButton("🎵 Musiqa"),
    KeyboardButton("🔙 Orqaga")
)

# Majburiy obuna tugmalari
majburiy_obuna_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
majburiy_obuna_keyboard.add(
    KeyboardButton("➕ Kanal qo'shish"),
    KeyboardButton("➖ Kanalni olib tashlash"),
    KeyboardButton("📋 Kanallar ro'yxati"),
    KeyboardButton("🔙 Orqaga")
)

# State guruhlari
class FileUploadStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_file = State()

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


@dp.message_handler(Command("cancel"), state="*")
async def cancel_handler(message: Message, state: FSMContext):
    """Foydalanuvchi har qanday holatdan chiqadi va admin panelga qaytadi."""
    if message.from_user.id in ADMINS:
        await state.finish()  # Barcha holatlarni tugatish
        await message.answer("🚫 Bekor qilindi. Siz bosh menyudasiz.", reply_markup=admin_keyboard)
    else:
        await message.answer("Siz admin emassiz.")


@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    user = message.from_user
    logger.info(f"Foydalanuvchi {user.id} start bosdi.")
    add_user(user.id, user.first_name, user.last_name, user.username)

    is_sub = await check_subscription(user.id)
    if not is_sub:
        channels = get_channels()
        keyboard = InlineKeyboardMarkup(row_width=1)
        
        for channel in channels:
            keyboard.add(InlineKeyboardButton(
                text=f"Obuna bo'lish ➡️ @{channel}",
                url=f"https://t.me/{channel}"
            ))
        
        keyboard.add(InlineKeyboardButton(
            text="✅ Obuna bo'ldim",
            callback_data="check_subscription"
        ))
        
        await message.answer(
            "⚠️ Botdan foydalanish uchun quyidagi kanal(lar)ga obuna bo'ling:",
            reply_markup=keyboard
        )
        return

    if user.id in ADMINS:
        await message.answer("👨‍💻 Admin panelga xush kelibsiz!", reply_markup=admin_keyboard)
    else:
        await message.answer("UZ ✅ Salom! Botga xush kelibsiz. Fayl kodini kiriting:\nRU ✅ Привет! Добро пожаловать в бота. Введите код файла:\nKK ✅ Cәлем! Ботқа қош келдіңіз. Файл кодын енгізіңіз:\nKY ✅ Салам! Ботко кош келиңиз. Файл кодун киргизиңиз:\nTK ✅ Salam! Bota hoş geldiňiz. Faýl koduny giriziň:\nHY ✅ Բարև! Բարի գալուստ բոտ: Մուտքագրեք ֆայլի կոդը:\nTG ✅ Салом! Хуш омадед ба бот. Рамзи файлро ворид кунед:" )

@dp.callback_query_handler(text="check_subscription")
async def check_subscription_callback(callback: types.CallbackQuery):
    messages = {
        "uz": "❌ Hali barcha kanallarga obuna bo‘lmagansiz.",
        "ru": "❌ Вы еще не подписались на все каналы.",
        "kk": "❌ Сіз әлі барлық арналарға жазылған жоқсыз.",
        "ky": "❌ Сиз дагы бардык каналдарга катталган жоксуз.",
        "tk": "❌ Siz entek ähli kanallara agza bolmadyňyz.",
        "hy": "❌ Դուք դեռ բոլոր ալիքներին բաժանորդագրված չեք.",
        "tg": "❌ Шумо ҳоло ба ҳамаи каналҳо обуна нашудаед."
    }

    if await check_subscription(callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer("✅ Obuna tekshirildi! Fayl kodini kiriting:")
    else:
        user_lang = callback.from_user.language_code
        warning_message = messages.get(user_lang, messages["uz"])  # Default O‘zbekcha

        await callback.answer(warning_message, show_alert=True)

@dp.callback_query_handler(lambda query: True)
async def check_subscription_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    if await check_subscription(user_id):
        await bot.answer_callback_query(callback_query.id, "Siz barcha kanallarga obuna bo'lgansiz! Rahmat!", show_alert=True)
    else:
        await bot.answer_callback_query(callback_query.id, "Iltimos, barcha kanallarga obuna bo'ling!", show_alert=True)

        


@dp.message_handler(lambda message: message.text.isdigit())
async def get_file_by_code(message: types.Message):
    user_id = message.from_user.id
    
    # Obunani tekshirish
    is_sub = await check_subscription(user_id)
    if not is_sub:
        channels = get_channels()
        keyboard = InlineKeyboardMarkup(row_width=1)
        
        for channel in channels:
            keyboard.add(InlineKeyboardButton(
                text=f"Obuna bo'lish ➡️ @{channel}",
                url=f"https://t.me/{channel}"
            ))
        
        keyboard.add(InlineKeyboardButton(
            text="✅ Obuna bo'ldim",
            callback_data="check_subscription"
        ))
        
        await message.answer(
            "⚠️ Botdan foydalanish uchun quyidagi kanal(lar)ga obuna bo'ling:",
            reply_markup=keyboard
        )
        return

    # Faylni yuborish
    file_code = message.text.strip()
    file_data = get_file(file_code)
    
    if file_data:
        file_id, file_link, file_type, caption = file_data
        
        if file_id:
            if file_type == "document":
                await message.answer_document(file_id, caption=caption)
            elif file_type == "photo":
                await message.answer_photo(file_id, caption=caption)
            elif file_type == "video":
                await message.answer_video(file_id, caption=caption)
            elif file_type == "audio":
                await message.answer_audio(file_id, caption=caption)
            elif file_type == "animation":
                await message.answer_animation(file_id, caption=caption)
            elif file_type == "voice":
                await message.answer_voice(file_id, caption=caption)
            elif file_type == "sticker":
                await message.answer_sticker(file_id)
            else:
                await message.answer("❌ Fayl topilmadi yoki noto‘g‘ri formatda saqlangan.")
        elif file_link:
            await message.answer(f"📥 '{file_code}' kodi uchun havola:\n{file_link}")
        else:
            await message.answer("❌ Fayl topilmadi yoki noto‘g‘ri formatda saqlangan.")
    else:
        await message.answer("❌ Bunday kod bilan fayl topilmadi.")


@dp.message_handler(lambda message: message.text == "📊 Statistika")
async def show_stats(message: types.Message):
    if message.from_user.id not in ADMINS:
        return  
    user_count = get_user_count()
    await message.answer(f"📊 Botdagi umumiy foydalanuvchilar soni: {user_count} ta")

@dp.message_handler(lambda message: message.text == "📥 Excelni yuklash")
async def download_excel(message: types.Message):
    if message.from_user.id not in ADMINS:
        return  
    users = get_all_users()
    df = pd.DataFrame(users, columns=["ID", "Telegram ID", "Ism", "Familiya", "Username", "Ro‘yxatdan o‘tgan vaqt"])
    df.to_excel("users.xlsx", index=False)
    with open("users.xlsx", "rb") as file:
        await message.answer_document(file, caption="📥 Foydalanuvchilar ro‘yxati (Excel)")

@dp.message_handler(lambda message: message.text == "📤 Fayl yuklash")
async def request_file_code(message: types.Message):
    if message.from_user.id not in ADMINS:
        return  
    await message.answer("📥 Fayl kodini kiriting (faqat raqam):")
    await FileUploadStates.waiting_for_code.set()

@dp.message_handler(state=FileUploadStates.waiting_for_code)
async def receive_file_code(message: types.Message, state: FSMContext):
    # Faqat raqamli qiymatni tekshirish
    if not message.text.isdigit():
        await message.answer("❌ Noto‘g‘ri format! Iltimos, faqat raqam kiriting.")
        return  # State ni saqlab qolamiz, admin qayta kiritish imkoniyatiga ega bo'ladi

    file_code = message.text.strip()
    
    # Fayl kodini tekshirish
    if is_file_code_exists(file_code):
        await message.answer(f"❌ {file_code} kodi allaqachon mavjud! Iltimos, boshqa kod kiriting.")
        return
    
    await state.update_data(file_code=file_code)
    await message.answer("📤 Endi faylni yuboring yoki bekor qilish uchun /cancel bosing:")
    await FileUploadStates.waiting_for_file.set()

@dp.message_handler(content_types=[
    types.ContentType.DOCUMENT,
    types.ContentType.PHOTO,
    types.ContentType.VIDEO,
    types.ContentType.AUDIO,
    types.ContentType.ANIMATION,
    types.ContentType.VOICE,
    types.ContentType.STICKER
], state=FileUploadStates.waiting_for_file)
async def receive_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    file_code = data.get("file_code")
    
    # Fayl kodini tekshirish
    if is_file_code_exists(file_code):
        await message.answer(f"❌ {file_code} kodi allaqachon mavjud! Iltimos, boshqa kod kiriting.")
        return
    
    # Fayl turini aniqlash va saqlash
    if message.document:
        file_id = message.document.file_id
        file_type = "document"
    elif message.photo:
        file_id = message.photo[-1].file_id  # Eng yuqori sifatli rasm
        file_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.audio:
        file_id = message.audio.file_id
        file_type = "audio"
    elif message.animation:
        file_id = message.animation.file_id
        file_type = "animation"
    elif message.voice:
        file_id = message.voice.file_id
        file_type = "voice"
    elif message.sticker:
        file_id = message.sticker.file_id
        file_type = "sticker"
    else:
        await message.answer("❌ Noto'g'ri format! Iltimos, faylni yuboring.")
        return
    
    # Caption ni olish
    caption = message.caption if message.caption else None
    
    # Faylni saqlash
    success = add_file(file_code, file_id=file_id, file_type=file_type, caption=caption)
    
    if success:
        await message.answer(f"✅ Fayl '{file_code}' kodi bilan saqlandi.")
    else:
        await message.answer(f"❌ {file_code} kodi allaqachon mavjud! Iltimos, boshqa kod kiriting.")
    
    await state.finish()

@dp.message_handler(state=FileUploadStates.waiting_for_file)
async def handle_wrong_input_file(message: types.Message):
    try:
        await message.answer("❌ Noto'g'ri format! Iltimos, faylni yuboring yoki amaliyotni bekor qilish uchun /cancel bosing:")
    except Exception as e:
        logger.error(f"Xatolik yuz berdi: {e}")


@dp.message_handler(lambda message: message.text.isdigit())  # Faqat raqam bo‘lsa
async def get_file_by_code(message: types.Message):
    file_code = message.text.strip()
    file_data = get_file(file_code)  # Bazadan fayl ma'lumotlarini olish
    
    if file_data:
        file_id, file_link = file_data  # file_id va file_link ni ajratib olish

        if file_id:
            # Agar file_id mavjud bo'lsa, faylni yuborish
            await message.answer_document(file_id, caption=f"📥 '{file_code}' kodi uchun fayl")
        elif file_link:
            # Agar file_link mavjud bo'lsa, havolani yuborish
            await message.answer(f"📥 '{file_code}' kodi uchun havola:\n{file_link}")
        else:
            # Agar ikkalasi ham mavjud bo'lmasa
            await message.answer("❌ Fayl topilmadi yoki noto‘g‘ri formatda saqlangan.")
    else:
        # Agar fayl topilmasa
        await message.answer("❌ Bunday kod bilan fayl topilmadi.")

@dp.message_handler(lambda message: message.text == "🔗 Majburiy obuna")
async def majburiy_obuna_menu(message: types.Message):
    if message.from_user.id not in ADMINS:
        return  
    await message.answer("Majburiy obuna sozlamalari:", reply_markup=majburiy_obuna_keyboard)

@dp.message_handler(lambda message: message.text == "📢 Reklama")
async def reklama_menu(message: types.Message):
    if message.from_user.id not in ADMINS:
        return  
    await message.answer("Reklama turini tanlang:", reply_markup=reklama_keyboard)

@dp.message_handler(lambda message: message.text == "🔙 Orqaga", state="*")
async def back_to_admin_menu(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return  
    await state.finish()  # Barcha holatlarni tugatish
    await message.answer("Admin panelga qaytdingiz.", reply_markup=admin_keyboard)

@dp.message_handler(lambda message: message.text == "📝 SMS")
async def request_sms_reklama(message: types.Message):
    if message.from_user.id not in ADMINS:
        return  
    await message.answer("Reklama matnini kiriting:")
    await ReklamaStates.waiting_for_sms.set()

@dp.message_handler(state=ReklamaStates.waiting_for_sms)
async def send_sms_reklama(message: types.Message, state: FSMContext):
    reklama_text = message.text
    users = get_all_users()
    
    for user in users:
        try:
            await bot.send_message(user[1], reklama_text)
        except Exception as e:
            logging.error(f"Foydalanuvchiga yuborishda xatolik: {user[1]} - {e}")

    await message.answer("✅ SMS reklama barcha foydalanuvchilarga yuborildi!")
    await state.finish()

@dp.message_handler(lambda message: message.text == "🖼 Rasm")
async def request_photo_reklama(message: types.Message):
    if message.from_user.id not in ADMINS:
        return  
    await message.answer("Rasmni yuboring:")
    await ReklamaStates.waiting_for_photo.set()

@dp.message_handler(content_types=types.ContentType.PHOTO, state=ReklamaStates.waiting_for_photo)
async def send_photo_reklama(message: types.Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.finish()  # Holatni tugatish
        await message.answer("Admin panelga qaytdingiz.", reply_markup=admin_keyboard)
    photo_id = message.photo[-1].file_id
    caption = message.caption if message.caption else ""
    users = get_all_users()

    for user in users:
        try:
            await bot.send_photo(user[1], photo_id, caption=caption)
        except Exception as e:
            if "bot was blocked by the user" in str(e):
                logging.warning(f"Foydalanuvchi botni bloklagan: {user[1]}")
            else:
                logging.error(f"Foydalanuvchiga rasm yuborishda xatolik: {user[1]} - {e}")

    await message.answer("✅ Rasm reklama barcha foydalanuvchilarga yuborildi!")
    await state.finish()

@dp.message_handler(state=ReklamaStates.waiting_for_photo)
async def handle_wrong_input_photo(message: types.Message):
    await message.answer("❌ Noto'g'ri format! Iltimos, rasmni yuboring.")


@dp.message_handler(lambda message: message.text == "🎥 Video")
async def request_video_reklama(message: types.Message):
    if message.from_user.id not in ADMINS:
        return  
    await message.answer("Videoni yuboring:")
    await ReklamaStates.waiting_for_video.set()

@dp.message_handler(content_types=types.ContentType.VIDEO, state=ReklamaStates.waiting_for_video)
async def send_video_reklama(message: types.Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.finish()  # Holatni tugatish
        await message.answer("Admin panelga qaytdingiz.", reply_markup=admin_keyboard)
    video_id = message.video.file_id
    caption = message.caption if message.caption else ""
    users = get_all_users()
    
    for user in users:
        try:
            await bot.send_video(user[1], video_id, caption=caption)
        except Exception as e:
            if "bot was blocked by the user" in str(e):
                logging.warning(f"Foydalanuvchi botni bloklagan: {user[1]}")
            else:
                logging.error(f"Foydalanuvchiga video yuborishda xatolik: {user[1]} - {e}")
    
    await message.answer("✅ Video reklama barcha foydalanuvchilarga yuborildi!")
    await state.finish()

@dp.message_handler(state=ReklamaStates.waiting_for_video)
async def handle_wrong_input_video(message: types.Message):
    await message.answer("❌ Noto'g'ri format! Iltimos, videoni yuboring.")



@dp.message_handler(lambda message: message.text == "📁 Fayl")
async def request_file_reklama(message: types.Message):
    if message.from_user.id not in ADMINS:
        return  
    await message.answer("Faylni yuboring:")
    await ReklamaStates.waiting_for_file.set()

@dp.message_handler(content_types=types.ContentType.DOCUMENT, state=ReklamaStates.waiting_for_file)
async def send_file_reklama(message: types.Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.finish()  # Holatni tugatish
        await message.answer("Admin panelga qaytdingiz.", reply_markup=admin_keyboard)
    document_id = message.document.file_id
    caption = message.caption if message.caption else ""
    users = get_all_users()
    
    for user in users:
        try:
            await bot.send_document(user[1], document_id, caption=caption)
        except Exception as e:
            if "bot was blocked by the user" in str(e):
                logging.warning(f"Foydalanuvchi botni bloklagan: {user[1]}")
            else:
                logging.error(f"Foydalanuvchiga fayl yuborishda xatolik: {user[1]} - {e}")
    
    await message.answer("✅ Fayl reklama barcha foydalanuvchilarga yuborildi!")
    await state.finish()

@dp.message_handler(state=ReklamaStates.waiting_for_file)
async def handle_wrong_input_file(message: types.Message):
    await message.answer("❌ Noto'g'ri format! Iltimos, faylni yuboring.")

@dp.message_handler(lambda message: message.text == "🎞 GIF")
async def request_gif_reklama(message: types.Message):
    if message.from_user.id not in ADMINS:
        return  
    await message.answer("GIFni yuboring:")
    await ReklamaStates.waiting_for_gif.set()

@dp.message_handler(content_types=types.ContentType.ANIMATION, state=ReklamaStates.waiting_for_gif)
async def send_gif_reklama(message: types.Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.finish()  # Holatni tugatish
        await message.answer("Admin panelga qaytdingiz.", reply_markup=admin_keyboard)
    gif_id = message.animation.file_id
    caption = message.caption if message.caption else ""
    users = get_all_users()
    
    for user in users:
        try:
            await bot.send_animation(user[1], gif_id, caption=caption)
        except Exception as e:
            if "bot was blocked by the user" in str(e):
                logging.warning(f"Foydalanuvchi botni bloklagan: {user[1]}")
            else:
                logging.error(f"Foydalanuvchiga GIF yuborishda xatolik: {user[1]} - {e}")
                
    
    await message.answer("✅ GIF reklama barcha foydalanuvchilarga yuborildi!")
    await state.finish()

@dp.message_handler(state=ReklamaStates.waiting_for_gif)
async def handle_wrong_input_gif(message: types.Message):
    await message.answer("❌ Noto'g'ri format! Iltimos, GIFni yuboring.")

@dp.message_handler(lambda message: message.text == "🎙 Ovozli xabar")
async def request_voice_reklama(message: types.Message):
    if message.from_user.id not in ADMINS:
        return  
    await message.answer("Ovozli xabarni yuboring:")
    await ReklamaStates.waiting_for_voice.set()

@dp.message_handler(content_types=types.ContentType.VOICE, state=ReklamaStates.waiting_for_voice)
async def send_voice_reklama(message: types.Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.finish()  # Holatni tugatish
        await message.answer("Admin panelga qaytdingiz.", reply_markup=admin_keyboard)
    voice_id = message.voice.file_id
    users = get_all_users()
    
    for user in users:
        try:
            await bot.send_voice(user[1], voice_id)
        except Exception as e:
            if "bot was blocked by the user" in str(e):
                logging.warning(f"Foydalanuvchi botni bloklagan: {user[1]}")
            else:
                logging.error(f"Foydalanuvchiga ovozli xabar yuborishda xatolik: {user[1]} - {e}")
    
    await message.answer("✅ Ovozli xabar reklama barcha foydalanuvchilarga yuborildi!")
    await state.finish()

@dp.message_handler(state=ReklamaStates.waiting_for_voice)
async def handle_wrong_input_voice(message: types.Message):
    await message.answer("❌ Noto'g'ri format! Iltimos, ovozli xabarni yuboring.")

@dp.message_handler(lambda message: message.text == "📍 Lokatsiya")
async def request_location_reklama(message: types.Message):
    if message.from_user.id not in ADMINS:
        return  
    await message.answer("Lokatsiyani yuboring:")
    await ReklamaStates.waiting_for_location.set()

@dp.message_handler(content_types=types.ContentType.LOCATION, state=ReklamaStates.waiting_for_location)
async def send_location_reklama(message: types.Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.finish()  # Holatni tugatish
        await message.answer("Admin panelga qaytdingiz.", reply_markup=admin_keyboard)
    location = message.location
    users = get_all_users()
    
    for user in users:
        try:
            await bot.send_location(user[1], location.latitude, location.longitude)
        except Exception as e:
            if "bot was blocked by the user" in str(e):
                logging.warning(f"Foydalanuvchi botni bloklagan: {user[1]}")
            else:
                logging.error(f"Foydalanuvchiga lokatsiya yuborishda xatolik: {user[1]} - {e}")
    
    await message.answer("✅ Lokatsiya reklama barcha foydalanuvchilarga yuborildi!")
    await state.finish()

@dp.message_handler(state=ReklamaStates.waiting_for_location)
async def handle_wrong_input_location(message: types.Message):
    await message.answer("❌ Noto'g'ri format! Iltimos, lokatsiyani yuboring.")

@dp.message_handler(lambda message: message.text == "🎵 Musiqa")
async def request_music_reklama(message: types.Message):
    if message.from_user.id not in ADMINS:
        return  
    await message.answer("Musiqani yuboring (mp3/m4a):")
    await ReklamaStates.waiting_for_music.set()

@dp.message_handler(content_types=types.ContentType.AUDIO, state=ReklamaStates.waiting_for_music)
async def send_music_reklama(message: types.Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.finish()  # Holatni tugatish
        await message.answer("Admin panelga qaytdingiz.", reply_markup=admin_keyboard)
    audio_id = message.audio.file_id
    caption = message.caption if message.caption else ""
    users = get_all_users()
    
    for user in users:
        try:
            await bot.send_audio(user[1], audio_id, caption=caption)
        except Exception as e:
            if "bot was blocked by the user" in str(e):
                logging.warning(f"Foydalanuvchi botni bloklagan: {user[1]}")
            else:
                logging.error(f"Foydalanuvchiga musiqa yuborishda xatolik: {user[1]} - {e}")
    
    await message.answer("✅ Musiqa reklama barcha foydalanuvchilarga yuborildi!")
    await state.finish()

@dp.message_handler(state=ReklamaStates.waiting_for_music)
async def handle_wrong_input_music(message: types.Message):
    await message.answer("❌ Noto'g'ri format! Iltimos, musiqani yuboring.")

@dp.message_handler(lambda message: message.text == "➕ Kanal qo'shish")
async def add_channel_handler(message: types.Message):
    if message.from_user.id not in ADMINS:
        return  
    await message.answer("Kanal username ni @ belgisi bilan kiriting (masalan, @channel_username):")
    await MajburiyObunaStates.waiting_for_channel_username.set()

@dp.message_handler(state=MajburiyObunaStates.waiting_for_channel_username)
async def process_add_channel(message: types.Message, state: FSMContext):
    # Agar "🔙 Orqaga" tugmasi bosilsa
    if message.text == "🔙 Orqaga":
        await state.finish()  # Holatni tugatish
        await message.answer("Admin panelga qaytdingiz.", reply_markup=admin_keyboard)
        return
    
    channel_username = message.text.strip()
    
    # Kanal username ni tekshirish
    if not channel_username.startswith("@"):
        await message.answer("❌ Noto'g'ri format! Iltimos, kanal username ni @ belgisi bilan kiriting (masalan, @channel_username).")
        return
    
    success = add_channel(channel_username)  # database.py dagi add_channel funksiyasi
    
    if success:
        await message.answer(f"✅ {channel_username} kanali qo'shildi!", reply_markup=admin_keyboard)
    else:
        await message.answer(f"❌ {channel_username} kanali allaqachon mavjud!", reply_markup=admin_keyboard)
    
    await state.finish()  # State ni tugatish



@dp.message_handler(lambda message: message.text == "➖ Kanalni olib tashlash")
async def remove_channel_handler(message: types.Message):
    if message.from_user.id not in ADMINS:
        return  
    await message.answer("Olib tashlash uchun kanal username ni kiriting (masalan, @channel_username):")
    await MajburiyObunaStates.waiting_for_channel_remove.set()

@dp.message_handler(state=MajburiyObunaStates.waiting_for_channel_remove)
async def process_remove_channel(message: types.Message, state: FSMContext):

    if message.text == "🔙 Orqaga":
        await state.finish()  # Holatni tugatish
        await message.answer("Admin panelga qaytdingiz.", reply_markup=admin_keyboard)
        return

    channel_username = message.text.strip().lstrip('@')
    success = remove_channel(channel_username)  # database.py dagi remove_channel funksiyasi
    
    if success:
        await message.answer(f"✅ @{channel_username} kanali olib tashlandi!", reply_markup=admin_keyboard)
    else:
        await message.answer(f"❌ @{channel_username} kanali topilmadi!", reply_markup=admin_keyboard)
    
    await state.finish()  # State ni tugatish


@dp.message_handler(lambda message: message.text == "📋 Kanallar ro'yxati")
async def list_channels_handler(message: types.Message):
    if message.from_user.id not in ADMINS:
        return  
    channels = get_channels()
    
    if channels:
        response = "📋 Majburiy obuna kanallari:\n" + "\n".join([f"👉 @{ch}" for ch in channels])
    else:
        response = "❌ Hech qanday kanal qo'shilmagan"
    
    await message.answer(response, reply_markup=admin_keyboard)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)