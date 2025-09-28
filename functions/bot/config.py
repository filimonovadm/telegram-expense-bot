import os
from dotenv import load_dotenv

load_dotenv()

# The environment is now controlled by an environment variable.
# Set ENV='test' in your local .env file for testing.
ENV = os.getenv('ENV', 'prod')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID_PROD = int(os.getenv('CHAT_ID_PROD'))

chat_id_test_str = os.getenv('CHAT_ID_TEST')
CHAT_ID_TEST = int(chat_id_test_str) if chat_id_test_str else None

if ENV == 'prod':
    ACTIVE_CHAT_ID = CHAT_ID_PROD
    INACTIVE_CHAT_ID = CHAT_ID_TEST
else: # ENV == 'test'
    if not CHAT_ID_TEST:
        raise ValueError("Ошибка: Запуск в режиме 'test' требует наличия CHAT_ID_TEST в .env файле.")
    ACTIVE_CHAT_ID = CHAT_ID_TEST
    INACTIVE_CHAT_ID = CHAT_ID_PROD

# The credential file is now inside the functions directory
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
FUNCTIONS_DIR = os.path.dirname(BOT_DIR)
FIREBASE_CREDENTIALS = os.path.join(FUNCTIONS_DIR, 'firebase_credentials.json')
