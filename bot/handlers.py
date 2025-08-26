import logging
import sqlite3
from telegram import Update, ParseMode, Bot
from telegram.error import BadRequest
from telegram.ext import CallbackContext
from .config import DB_FILE, ENV, ACTIVE_CHAT_ID
from .database import add_or_update_user

logger = logging.getLogger(__name__)

def send_startup_notification(bot: Bot):
    if ACTIVE_CHAT_ID:
        try:
            bot.send_message(chat_id=ACTIVE_CHAT_ID, text=f"✅ Бот запущен и снова в сети! (v2.0 - {ENV.upper()})")
            logger.info(f"Отправлено уведомление о запуске в чат {ACTIVE_CHAT_ID}")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление о запуске: {e}")

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        f'Привет! Я бот для учета расходов (v1.7 - {ENV.upper()}).\n\n'
        'Чтобы удалить запись, ответьте на нее командой `/delete`.',
        parse_mode=ParseMode.MARKDOWN
    )

def ping(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Pong! Я в сети и готов к работе.")

def get_chat_id(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    update.message.reply_text(f"ID этого чата: `{chat_id}`")

def start_tracking(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT message_id FROM chats WHERE chat_id = ?", (chat_id,))
    if cursor.fetchone():
        update.message.reply_text('Учет расходов уже ведется.')
        conn.close()
        return

    message_text = '📊 **Учет общих расходов**\n\nРасходы пока не заведены.'
    sent_message = update.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN)
    try:
        context.bot.pin_chat_message(chat_id, sent_message.message_id)
        cursor.execute("INSERT INTO chats (chat_id, message_id) VALUES (?, ?)", (chat_id, sent_message.message_id))
        conn.commit()
        logger.info(f"Начат учет в чате {chat_id}")
    except BadRequest:
        update.message.reply_text('Не удалось закрепить сообщение. Сделайте меня администратором.')
    finally:
        conn.close()

def reset_tracking(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT message_id FROM chats WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    if row:
        try:
            context.bot.unpin_chat_message(chat_id, row[0])
        except Exception: pass
        cursor.execute("DELETE FROM expenses WHERE chat_id = ?", (chat_id,))
        cursor.execute("DELETE FROM debts WHERE chat_id = ?", (chat_id,))
        cursor.execute("DELETE FROM chats WHERE chat_id = ?", (chat_id,))
        conn.commit()
        update.message.reply_text('Все расходы и долги сброшены.')
    else:
        update.message.reply_text('Учет не ведется.')
    conn.close()

def owe(update: Update, context: CallbackContext) -> None:
    message = update.message
    if not message.reply_to_message:
        message.reply_text("Ошибка: нужно ответить на сообщение того, кому вы должны.")
        return
    try:
        debtor, creditor = message.from_user, message.reply_to_message.from_user
        add_or_update_user(debtor.id, debtor.first_name)
        add_or_update_user(creditor.id, creditor.first_name)

        amount = float(context.args[0].replace(',', '.'))
        reason = ' '.join(context.args[1:]) if len(context.args) > 1 else 'Без описания'

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO debts (message_id, chat_id, from_user_id, to_user_id, amount, reason) VALUES (?, ?, ?, ?, ?, ?)",
                       (message.message_id, message.chat_id, debtor.id, creditor.id, amount, reason))
        conn.commit()
        conn.close()

        message.reply_text(f"✅ Записан долг: {debtor.first_name} должен(на) {creditor.first_name} {amount:.2f} лир ({reason}).")
        update_summary_message(context.bot, message.chat_id)
    except (IndexError, ValueError):
        message.reply_text("Неверный формат. Используйте: /owe <сумма> <описание>")
    except Exception as e:
        logger.error(f"Ошибка в команде /owe: {e}")
        message.reply_text("Произошла ошибка при записи долга.")

def handle_expense(update: Update, context: CallbackContext) -> None:
    message = update.message
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2: return
        amount = float(parts[0].replace(',', '.'))
        if amount <= 0: return

        user = message.from_user
        add_or_update_user(user.id, user.first_name)

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("SELECT SUM(amount) FROM expenses WHERE chat_id = ? AND user_id = ?", (message.chat_id, user.id))
        total_before = cursor.fetchone()[0] or 0.0

        cursor.execute("INSERT INTO expenses (message_id, chat_id, user_id, amount, description) VALUES (?, ?, ?, ?, ?)",
                       (message.message_id, message.chat_id, user.id, amount, parts[1]))
        conn.commit()
        conn.close()

        total_after = total_before + amount
        reply_text = (f"✅ Записал!\n\n**{user.first_name}**:\nБыло потрачено: {total_before:.2f} лир\nСтало потрачено: {total_after:.2f} лир")
        message.reply_text(reply_text, parse_mode=ParseMode.MARKDOWN)
        update_summary_message(context.bot, message.chat_id)
    except (ValueError, IndexError): pass
    except Exception as e:
        logger.error(f"Непредвиденная ошибка в handle_expense: {e}", exc_info=True)

def delete_entry(update: Update, context: CallbackContext) -> None:
    message = update.message
    if not message.reply_to_message:
        message.reply_text("Чтобы удалить запись, нужно ответить на нее командой /delete")
        return

    reply_to_id = message.reply_to_message.message_id
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM expenses WHERE message_id = ?", (reply_to_id,))
    if cursor.rowcount > 0:
        deleted_info = "Расход удален."
    else:
        cursor.execute("DELETE FROM debts WHERE message_id = ?", (reply_to_id,))
        if cursor.rowcount > 0:
            deleted_info = "Долг удален."
        else:
            deleted_info = "Не нашел такой записи в базе."

    conn.commit()
    conn.close()
    message.reply_text(f"✅ {deleted_info}")
    if deleted_info != "Не нашел такой записи в базе.":
        update_summary_message(context.bot, message.chat_id)

def update_summary_message(bot: Bot, chat_id: int) -> None:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT message_id FROM chats WHERE chat_id = ?", (chat_id,))
    chat_row = cursor.fetchone()
    if not chat_row:
        conn.close()
        return

    summary_message_id = chat_row['message_id']

    user_totals, user_names, final_balances = {}, {}, {}

    cursor.execute("SELECT user_id, name FROM users")
    for row in cursor.fetchall():
        user_names[row['user_id']] = row['name']

    cursor.execute("SELECT user_id, SUM(amount) as total FROM expenses WHERE chat_id = ? GROUP BY user_id", (chat_id,))
    for row in cursor.fetchall():
        user_totals[row['user_id']] = row['total']

    all_user_ids = set(user_totals.keys())
    cursor.execute("SELECT from_user_id, to_user_id FROM debts WHERE chat_id = ?", (chat_id,))
    for row in cursor.fetchall():
        all_user_ids.add(row['from_user_id'])
        all_user_ids.add(row['to_user_id'])

    for user_id in all_user_ids:
        user_totals.setdefault(user_id, 0.0)

    summary_lines = []
    if any(v > 0 for v in user_totals.values()):
        total_spent = sum(user_totals.values())
        num_users = len(user_totals)
        average_spent = total_spent / num_users if num_users > 0 else 0

        summary_lines.append("*Общие расходы:*")
        for user_id, total in user_totals.items():
            final_balances[user_id] = total - average_spent
            summary_lines.append(f"  - {user_names.get(user_id, 'Unknown')}: {total:.2f} лир")
        summary_lines.extend([f"\n*Всего потрачено:* {total_spent:.2f} лир", f"*Средний расход:* {average_spent:.2f} лир"])

    cursor.execute("SELECT d.from_user_id, u1.name as from_name, d.to_user_id, u2.name as to_name, d.amount, d.reason FROM debts d JOIN users u1 ON d.from_user_id = u1.user_id JOIN users u2 ON d.to_user_id = u2.user_id WHERE d.chat_id = ?", (chat_id,))
    debts_data = cursor.fetchall()
    if debts_data:
        summary_lines.append("\n*Личные долги:*")
        for row in debts_data:
            summary_lines.append(f"  - {row['from_name']} → {row['to_name']}: {row['amount']:.2f} лир ({row['reason']})")
            final_balances[row['from_user_id']] = final_balances.get(row['from_user_id'], 0) - row['amount']
            final_balances[row['to_user_id']] = final_balances.get(row['to_user_id'], 0) + row['amount']

    if final_balances:
        summary_lines.append("\n*ИТОГОВЫЙ БАЛАНС:*")
        balances_list = [{'name': user_names.get(uid, f'User {uid}'), 'balance': bal} for uid, bal in final_balances.items()]
        positive = sorted([b for b in balances_list if b['balance'] > 0.01], key=lambda x: x['balance'], reverse=True)
        negative = sorted([b for b in balances_list if b['balance'] < -0.01], key=lambda x: x['balance'])
        i, j = 0, 0
        while i < len(negative) and j < len(positive):
            debtor, creditor = negative[i], positive[j]
            amount = min(-debtor['balance'], creditor['balance'])
            summary_lines.append(f"  - {debtor['name']} должен(на) {creditor['name']}: {amount:.2f} лир")
            debtor['balance'] += amount
            creditor['balance'] -= amount
            if abs(debtor['balance']) < 0.01: i += 1
            if abs(creditor['balance']) < 0.01: j += 1

    final_text = '📊 **Учет общих расходов**\n\n' + ('Расходы пока не заведены.' if not summary_lines else '```\n' + '\n'.join(summary_lines) + '\n```')

    try:
        bot.edit_message_text(chat_id=chat_id, message_id=summary_message_id, text=final_text, parse_mode=ParseMode.MARKDOWN_V2)
    except BadRequest as e:
        if 'Message to edit not found' in str(e):
            logger.warning("Старое закрепленное сообщение не найдено. Создаю новое.")
            try:
                bot.unpin_all_chat_messages(chat_id=chat_id)
            except Exception: pass
            new_message = bot.send_message(chat_id=chat_id, text=final_text, parse_mode=ParseMode.MARKDOWN_V2)
            bot.pin_chat_message(chat_id=chat_id, message_id=new_message.message_id)
            cursor.execute("UPDATE chats SET message_id = ? WHERE chat_id = ?", (new_message.message_id, chat_id))
            conn.commit()
        elif "Message is not modified" not in str(e):
            pass
        else:
            logger.error(f"Ошибка BadRequest при обновлении сообщения: {e}")
    conn.close()

def inactive_chat_handler(update: Update, context: CallbackContext) -> None:
    if ENV == 'test':
        message = "Бот запущен в режиме разработки. Повторите попытку позже."
    else:
        message = "Это тестовый чат. Бот работает в основном режиме."
    update.message.reply_text(message)
