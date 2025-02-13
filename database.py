import sqlite3
from datetime import datetime

DB_NAME = "bot_database.db"

def create_tables():
    """Bazadagi jadvallarni yaratish."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Foydalanuvchilar jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        first_name TEXT,
        last_name TEXT,
        username TEXT,
        created_at TEXT
    )''')

    # Fayllar jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_code TEXT UNIQUE,
        file_id TEXT,
        file_link TEXT,
        file_type TEXT,
        caption TEXT,
        uploaded_at TEXT
    )''')

    # Kanallar jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE
    )''')

    conn.commit()
    conn.close()


def add_user(user_id, first_name, last_name, username):
    """Foydalanuvchini bazaga qo'shish."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''INSERT OR IGNORE INTO users (user_id, first_name, last_name, username, created_at) 
                      VALUES (?, ?, ?, ?, ?)''', 
                   (user_id, first_name, last_name, username, created_at))
    conn.commit()
    conn.close()

def get_user_count():
    """Foydalanuvchilar sonini qaytaradi."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_all_users():
    """Barcha foydalanuvchilarni qaytaradi."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    conn.close()
    return users

def is_file_code_exists(file_code):
    """Fayl kodi mavjudligini tekshiradi."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM files WHERE file_code = ?", (file_code,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0  # Agar 1 yoki undan ko'p bo'lsa, True qaytaradi

def add_file(file_code, file_id=None, file_link=None, file_type=None, caption=None):
    """Faylni bazaga qo'shish."""
    if is_file_code_exists(file_code):
        return False
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    uploaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''INSERT INTO files (file_code, file_id, file_link, file_type, caption, uploaded_at) 
                      VALUES (?, ?, ?, ?, ?, ?)''', 
                   (file_code, file_id, file_link, file_type, caption, uploaded_at))
    conn.commit()
    conn.close()
    return True


def get_file(file_code):
    """Fayl kodiga qarab faylni olish."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, file_link, file_type, caption FROM files WHERE file_code = ?", (file_code,))
    result = cursor.fetchone()
    conn.close()
    return result

def add_channel(channel_username):
    """Kanalni bazaga qo'shish."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO channels (username) VALUES (?)", (channel_username.lstrip('@'),))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Kanal allaqachon mavjud
    finally:
        conn.close()

def remove_channel(channel_username):
    """Kanalni bazadan olib tashlash."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM channels WHERE username = ?", (channel_username.lstrip('@'),))
    conn.commit()
    rows_deleted = cursor.rowcount
    conn.close()
    return rows_deleted > 0  # Agar 1 yoki undan ko'p qator o'chirilsa, True qaytaradi

def get_channels():
    """Barcha kanallarni qaytaradi."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM channels")
    channels = [row[0] for row in cursor.fetchall()]
    conn.close()
    return channels

# Bazani yaratish
create_tables()