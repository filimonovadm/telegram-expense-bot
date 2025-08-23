import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from bot.config import TELEGRAM_BOT_TOKEN, ENV, ACTIVE_CHAT_ID, INACTIVE_CHAT_ID
from bot.database import setup_database
from bot.handlers import (
    start, ping, get_chat_id, start_tracking, reset_tracking,
    owe, delete_entry, handle_expense, inactive_chat_handler,
    send_startup_notification
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def main() -> None:
    setup_database()
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher

    send_startup_notification(updater.bot)

    active_chat_filter = Filters.chat(chat_id=ACTIVE_CHAT_ID)
    inactive_chat_filter = Filters.chat_type.groups & ~active_chat_filter

    dispatcher.add_handler(CommandHandler("start", start, filters=active_chat_filter))
    dispatcher.add_handler(CommandHandler("ping", ping, filters=active_chat_filter))
    dispatcher.add_handler(CommandHandler("getchatid", get_chat_id, filters=active_chat_filter))
    dispatcher.add_handler(CommandHandler("start_tracking", start_tracking, filters=active_chat_filter))
    dispatcher.add_handler(CommandHandler("reset", reset_tracking, filters=active_chat_filter))
    dispatcher.add_handler(CommandHandler("owe", owe, filters=active_chat_filter))
    dispatcher.add_handler(CommandHandler("delete", delete_entry, filters=active_chat_filter))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command & active_chat_filter, handle_expense))
    dispatcher.add_handler(MessageHandler(inactive_chat_filter, inactive_chat_handler))

    updater.start_polling(drop_pending_updates=False)
    logger.info(f"Бот запущен в режиме: {ENV.upper()}")
    updater.idle()

if __name__ == '__main__':
    main()
