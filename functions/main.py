#-*- coding: utf-8 -*-
import os
import flask
from firebase_functions import https_fn
from telegram import Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    Dispatcher,
    CallbackContext,
)

# Adjust imports to the new structure
from bot.config import TELEGRAM_BOT_TOKEN
from bot.database import initialize_firebase
from bot.handlers import (
    start, ping, get_chat_id, start_tracking,
    owe, delete_entry, handle_expense
)

# Initialize Firebase
initialize_firebase()

# Check for Token
if TELEGRAM_BOT_TOKEN is None:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in environment variables!")

# --- Bot and Dispatcher Setup ---
# We create these objects once globally
bot = Updater(TELEGRAM_BOT_TOKEN).bot
dispatcher = Dispatcher(bot, None, use_context=True)

# Register handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("ping", ping))
dispatcher.add_handler(CommandHandler("getchatid", get_chat_id))
dispatcher.add_handler(CommandHandler("start_tracking", start_tracking))
dispatcher.add_handler(CommandHandler("owe", owe))
dispatcher.add_handler(CommandHandler("delete", delete_entry))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command & Filters.chat_type.groups, handle_expense))
# --------------------------------

app = flask.Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handles incoming updates from Telegram."""
    if flask.request.method == "POST":
        update = Update.de_json(flask.request.get_json(force=True), bot)
        dispatcher.process_update(update)
    return "ok"

@https_fn.on_request()
def turkeybot(req: https_fn.Request) -> https_fn.Response:
    """The main Cloud Function that wraps the Flask app."""
    with app.request_context(req.environ):
        return app.full_dispatch_request()
