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
CHAT_ID_TEST = int(os.getenv('CHAT_ID_TEST'))

ACTIVE_CHAT_ID = CHAT_ID_PROD if ENV == 'prod' else CHAT_ID_TEST
INACTIVE_CHAT_ID = CHAT_ID_TEST if ENV == 'prod' else CHAT_ID_PROD

DB_FILE = 'bot_data.db'
