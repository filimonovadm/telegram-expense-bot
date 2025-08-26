import os
import argparse
from dotenv import load_dotenv

load_dotenv()

parser = argparse.ArgumentParser(description="Telegram Expense Bot")
parser.add_argument('--env', choices=['prod', 'test'], default='prod', help='Specify the environment: prod or test')
args = parser.parse_args()
ENV = args.env

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID_PROD = int(os.getenv('CHAT_ID_PROD'))

chat_id_test_str = os.getenv('CHAT_ID_TEST')
CHAT_ID_TEST = int(chat_id_test_str) if chat_id_test_str else None

if ENV == 'prod':
    ACTIVE_CHAT_ID = CHAT_ID_PROD
    INACTIVE_CHAT_ID = CHAT_ID_TEST
else: # ENV == 'test'
    if not CHAT_ID_TEST:
        raise ValueError("Ошибка: Запуск в режиме '--env test' требует наличия CHAT_ID_TEST в .env файле.")
    ACTIVE_CHAT_ID = CHAT_ID_TEST
    INACTIVE_CHAT_ID = CHAT_ID_PROD

DB_FILE = 'bot_data.db'
