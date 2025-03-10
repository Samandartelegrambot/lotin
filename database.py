import sqlite3
import logging
from datetime import datetime

DB_NAME = "bot_database.db"

def create_tables():
    """Ma'lumotlar bazasida jadvallarni va indekslarni yaratadi."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Users jadvali
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            created_at TEXT
        )''')
        # Files jadvali
        cursor.execute('''CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_code TEXT UNIQUE,
            file_id TEXT,
            file_link TEXT,
            file_type TEXT,
            caption TEXT,
            uploaded_at TEXT
        )''')
        # Channels jadvali
        cursor.execute('''CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE
        )''')
        # File_requests jadvali
        cursor.execute('''CREATE TABLE IF NOT EXISTS file_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            file_code TEXT,
            requested_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )''')

        # Indekslar qo‘shish
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_file_code ON files(file_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_requests_user_id ON file_requests(user_id)")

        conn.commit()



def add_user(user_id, first_name, last_name, username):
    """Foydalanuvchini qo'shadi."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''INSERT OR IGNORE INTO users (user_id, first_name, last_name, username, created_at) 
                          VALUES (?, ?, ?, ?, ?)''', 
                       (user_id, first_name, last_name, username, created_at))
        conn.commit()

def get_user_count():
    """Foydalanuvchilar sonini qaytaradi."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        return cursor.fetchone()[0]

def get_all_users():
    """Barcha foydalanuvchilarni qaytaradi."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        return cursor.fetchall()

def is_file_code_exists(file_code):
    """Fayl kodi mavjudligini tekshiradi."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM files WHERE file_code = ?", (file_code,))
        return cursor.fetchone()[0] > 0

def add_file(file_code, file_id=None, file_link=None, file_type=None, caption=None):
    """Faylni qo'shadi."""
    if is_file_code_exists(file_code):
        return False
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        uploaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor.execute('''INSERT INTO files (file_code, file_id, file_link, file_type, caption, uploaded_at) 
                              VALUES (?, ?, ?, ?, ?, ?)''', 
                           (file_code, file_id, file_link, file_type, caption, uploaded_at))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Fayl qo‘shishda xatolik: {e}")
            return False

def get_file(file_code):
    """Fayl ma'lumotlarini qaytaradi."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT file_id, file_link, file_type, caption FROM files WHERE file_code = ?", (file_code,))
        return cursor.fetchone()

def remove_file(file_code):
    """Faylni kod bo'yicha o'chiradi."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM files WHERE file_code = ?", (file_code,))
        conn.commit()
        return cursor.rowcount > 0

def add_channel(channel_username):
    """Majburiy obuna kanalini qo'shadi."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO channels (username) VALUES (?)", (channel_username.lstrip('@'),))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def remove_channel(channel_username):
    """Majburiy obuna kanalini o'chiradi."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM channels WHERE username = ?", (channel_username.lstrip('@'),))
        conn.commit()
        return cursor.rowcount > 0

def get_channels():
    """Barcha majburiy obuna kanallarini qaytaradi."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM channels")
        return [row[0] for row in cursor.fetchall()]

# Yangi funksiya: Fayl so‘rovini qo‘shish
def add_file_request(user_id, file_code):
    """Foydalanuvchi fayl so‘rovini qo‘shadi."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        requested_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor.execute('''INSERT INTO file_requests (user_id, file_code, requested_at) 
                              VALUES (?, ?, ?)''', 
                           (user_id, file_code, requested_at))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Fayl so‘rovi qo‘shishda xatolik: {e}")
            return False

# Yangi funksiya: Foydalanuvchi so‘rovlarini olish
def get_user_requests(user_id, start_date=None, end_date=None):
    """Foydalanuvchining barcha fayl so‘rovlarini qaytaradi, vaqt filtri bilan."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        query = "SELECT file_code, requested_at FROM file_requests WHERE user_id = ?"
        params = [user_id]
        if start_date:
            query += " AND requested_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND requested_at <= ?"
            params.append(end_date)
        cursor.execute(query, params)
        return cursor.fetchall()

# database.py faylining oxiriga qo‘shiladi
def get_all_file_codes(file_type=None):
    """Barcha fayl kodlarni yoki faqat ma'lum turdagi kodlarni qaytaradi."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        if file_type:
            cursor.execute("SELECT file_code, file_type, uploaded_at, caption FROM files WHERE file_type = ? ORDER BY uploaded_at DESC", (file_type,))
        else:
            cursor.execute("SELECT file_code, file_type, uploaded_at, caption FROM files ORDER BY uploaded_at DESC")
        return cursor.fetchall()

create_tables()
