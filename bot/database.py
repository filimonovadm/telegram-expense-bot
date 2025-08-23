import sqlite3
import logging
from .config import DB_FILE

logger = logging.getLogger(__name__)

def setup_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS chats (chat_id INTEGER PRIMARY KEY, message_id INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT NOT NULL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS expenses (message_id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL, amount REAL NOT NULL, description TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS debts (message_id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, from_user_id INTEGER NOT NULL, to_user_id INTEGER NOT NULL, amount REAL NOT NULL, reason TEXT)')
    conn.commit()
    conn.close()
    logger.info("База данных готова к работе.")

def add_or_update_user(user_id, name):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, name) VALUES (?, ?)", (user_id, name))
    conn.commit()
    conn.close()
