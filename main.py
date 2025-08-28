import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from bot.config import TELEGRAM_BOT_TOKEN
from bot.database import setup_database
from bot.handlers import (
    start, ping, get_chat_id, start_tracking,
    owe, delete_entry, handle_expense
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def main() -> None:
    setup_database()
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("ping", ping))
    dispatcher.add_handler(CommandHandler("getchatid", get_chat_id))
    dispatcher.add_handler(CommandHandler("start_tracking", start_tracking))
    dispatcher.add_handler(CommandHandler("owe", owe))
    dispatcher.add_handler(CommandHandler("delete", delete_entry))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command & Filters.group, handle_expense))

    updater.start_polling(drop_pending_updates=False)
    logger.info("Публичный бот запущен...")
    updater.idle()

if __name__ == '__main__':
    main()
