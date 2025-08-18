import logging
import json
import os
from dotenv import load_dotenv
from telegram import Update, ParseMode, Bot
from telegram.error import BadRequest, TimedOut
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID_FOR_NOTIFICATIONS = os.getenv('CHAT_ID_FOR_NOTIFICATIONS')

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
DATA_FILE = 'data.json'
chat_data = {}

def save_data():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(chat_data, f, ensure_ascii=False, indent=4)
        logger.info("Данные успешно сохранены.")
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных: {e}")

def load_data():
    global chat_data
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            chat_data = json.load(f)
            chat_data = {int(k): v for k, v in chat_data.items()}
            logger.info("Данные успешно загружены.")
    except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
        logger.error(f"Ошибка при загрузке данных: {e}. Начинаем с пустыми данными.")
        chat_data = {}

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        'Привет! Я бот для учета расходов (v1.3).\n\n'
        '✅ *Новое*: Чтобы удалить расход/долг (включая старые!), ответьте (`Reply`) на него командой `/delete`.\n\n'
        '✅ *Общие расходы*: `сумма описание`\n'
        '✅ *Личный долг*: Ответьте на сообщение и напишите:\n`/owe сумма описание`',
        parse_mode=ParseMode.MARKDOWN
    )

def get_chat_id(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    update.message.reply_text(f"ID этого чата: `{chat_id}`")

def start_tracking(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    if chat_id in chat_data:
        update.message.reply_text('Учет расходов уже ведется.')
        return
    message_text = '📊 **Учет общих расходов**\n\nРасходы пока не заведены.'
    sent_message = update.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN)
    try:
        context.bot.pin_chat_message(chat_id, sent_message.message_id)
        chat_data[chat_id] = {'message_id': sent_message.message_id, 'users': {}, 'debts': []}
        save_data()
        logger.info(f"Начат учет в чате {chat_id}")
    except BadRequest:
        update.message.reply_text('Не удалось закрепить сообщение. Сделайте меня администратором.')

def reset_tracking(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    if chat_id in chat_data:
        try:
            context.bot.unpin_chat_message(chat_id, chat_data[chat_id]['message_id'])
        except Exception as e: logger.error(f"Не удалось открепить сообщение: {e}")
        del chat_data[chat_id]
        save_data()
        update.message.reply_text('Все расходы и долги сброшены.')
    else:
        update.message.reply_text('Учет не ведется.')

def reset_debts(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    if chat_id in chat_data and 'debts' in chat_data[chat_id]:
        chat_data[chat_id]['debts'] = []
        save_data()
        update.message.reply_text('Личные долги сброшены.')
        update_summary_message(context.bot, chat_id)
    else:
        update.message.reply_text('Учет не ведется.')

def owe(update: Update, context: CallbackContext) -> None:
    message = update.message
    if not message.reply_to_message:
        message.reply_text("Ошибка: нужно ответить на сообщение того, кому вы должны.")
        return
    chat_id = message.chat_id
    if chat_id not in chat_data:
        message.reply_text("Сначала начните учет командой /start_tracking")
        return
    try:
        debtor, creditor = message.from_user, message.reply_to_message.from_user
        if debtor.id == creditor.id:
            message.reply_text("Нельзя быть должным самому себе.")
            return
        amount = float(context.args[0].replace(',', '.'))
        reason = ' '.join(context.args[1:]) if len(context.args) > 1 else 'Без описания'
        if amount <= 0:
            message.reply_text("Сумма должна быть > 0.")
            return
        debt_record = {'from_id': str(debtor.id), 'from_name': debtor.first_name, 'to_id': str(creditor.id), 'to_name': creditor.first_name, 'amount': amount, 'reason': reason, 'message_id': message.message_id}
        chat_data[chat_id].setdefault('debts', []).append(debt_record)
        save_data()
        message.reply_text(f"✅ Записан долг: {debtor.first_name} должен(на) {creditor.first_name} {amount:.2f} лир ({reason}).")
        update_summary_message(context.bot, chat_id)
    except (IndexError, ValueError):
        message.reply_text("Неверный формат. Используйте: /owe <сумма> <описание>")
    except TimedOut:
        logger.warning("Произошел тайм-аут. Telegram должен повторить отправку.")
    except Exception as e:
        logger.error(f"Ошибка в команде /owe: {e}")
        message.reply_text("Произошла непредвиденная ошибка при записи долга.")

def update_summary_message(bot: Bot, chat_id: int) -> None:
    if chat_id not in chat_data: return
    data = chat_data[chat_id]
    user_totals = {}
    user_names = {}
    users_data = data.get('users', {})
    for user_id_str, user_info in users_data.items():
        user_id = int(user_id_str)
        user_names[user_id] = user_info['name']
        if 'expenses' in user_info:
            total = sum(expense['amount'] for expense in user_info.get('expenses', []))
        else:
            total = user_info.get('total', 0.0)
        user_totals[user_id] = total
    debts_data = data.get('debts', [])
    for debt in debts_data:
        user_names.setdefault(int(debt['from_id']), debt['from_name'])
        user_names.setdefault(int(debt['to_id']), debt['to_name'])
    summary_lines, final_balances = [], {}
    if user_totals:
        total_spent = sum(user_totals.values())
        num_users = len(user_totals) if len(user_totals) > 0 else 1
        average_spent = total_spent / num_users
        summary_lines.append("*Общие расходы:*")
        for user_id, total in user_totals.items():
            final_balances[user_id] = total - average_spent
            summary_lines.append(f"  - {user_names.get(user_id, 'Unknown')}: {total:.2f} лир")
        summary_lines.extend([f"\n*Всего потрачено:* {total_spent:.2f} лир", f"*Средний расход:* {average_spent:.2f} лир"])
    if debts_data:
        if not summary_lines or "\n*Личные долги:*" not in summary_lines:
             summary_lines.append("\n*Личные долги:*")
        for debt in debts_data:
            from_id, to_id = int(debt['from_id']), int(debt['to_id'])
            summary_lines.append(f"  - {debt['from_name']} → {debt['to_name']}: {debt['amount']:.2f} лир ({debt['reason']})")
            final_balances[from_id] = final_balances.get(from_id, 0) - debt['amount']
            final_balances[to_id] = final_balances.get(to_id, 0) + debt['amount']
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
        bot.edit_message_text(chat_id=chat_id, message_id=data['message_id'], text=final_text, parse_mode=ParseMode.MARKDOWN_V2)
    except BadRequest: pass

def handle_expense(update: Update, context: CallbackContext) -> None:
    message = update.message
    chat_id = message.chat_id
    if chat_id not in chat_data: return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2: return
        amount = float(parts[0].replace(',', '.'))
        if amount <= 0: return
        user = message.from_user
        user_id_str = str(user.id)
        users = chat_data[chat_id].setdefault('users', {})
        if user_id_str not in users:
            users[user_id_str] = {'name': user.first_name, 'expenses': []}
        if 'total' in users[user_id_str]:
            old_total = users[user_id_str].get('total', 0.0)
            users[user_id_str]['expenses'] = []
            if old_total > 0:
                users[user_id_str]['expenses'].append({'amount': old_total, 'description': 'Сумма из предыдущих версий', 'message_id': 0})
            del users[user_id_str]['total']
        total_before = sum(exp['amount'] for exp in users[user_id_str].get('expenses', []))
        expense_record = {'amount': amount, 'description': parts[1], 'message_id': message.message_id}
        users[user_id_str].setdefault('expenses', []).append(expense_record)
        save_data()
        total_after = total_before + amount
        logger.info(f"Добавлен общий расход {amount} от {user.first_name} в чате {chat_id}")
        reply_text = (f"✅ Записал!\n\n**{user.first_name}**:\nБыло потрачено: {total_before:.2f} лир\nСтало потрачено: {total_after:.2f} лир")
        message.reply_text(reply_text, parse_mode=ParseMode.MARKDOWN)
        update_summary_message(context.bot, chat_id)
    except (ValueError, IndexError): pass
    except TimedOut: logger.warning("Произошел тайм-аут при обработке расхода. Ждем повтора.")

def delete_entry(update: Update, context: CallbackContext) -> None:
    message = update.message
    if not message.reply_to_message:
        message.reply_text("Чтобы удалить запись, нужно ответить на нее командой /delete")
        return
    chat_id = message.chat_id
    if chat_id not in chat_data: return

    reply_to_id = message.reply_to_message.message_id
    deleted, deleted_info = False, ""

    debts = chat_data[chat_id].get('debts', [])
    new_debts = [d for d in debts if d.get('message_id') != reply_to_id]
    if len(new_debts) < len(debts):
        deleted_debt = next((d for d in debts if d.get('message_id') == reply_to_id), None)
        deleted_info = f"Долг: {deleted_debt['from_name']} → {deleted_debt['to_name']} на {deleted_debt['amount']:.2f} лир"
        deleted = True
        chat_data[chat_id]['debts'] = new_debts

    if not deleted:
        for user_data in chat_data[chat_id].get('users', {}).values():
            expenses = user_data.get('expenses', [])
            new_expenses = [e for e in expenses if e.get('message_id') != reply_to_id]
            if len(new_expenses) < len(expenses):
                deleted_expense = next((e for e in expenses if e.get('message_id') == reply_to_id), None)
                deleted_info = f"Расход от {user_data['name']} на {deleted_expense['amount']:.2f} лир"
                deleted = True
                user_data['expenses'] = new_expenses
                break

    if not deleted:
        replied_message_text = message.reply_to_message.text
        replied_author_id = message.reply_to_message.from_user.id

        if replied_message_text.lower().startswith('/owe'):
            try:
                parts = replied_message_text.split(maxsplit=2)
                amount = float(parts[1].replace(',', '.'))
                reason = parts[2] if len(parts) > 2 else 'Без описания'

                debt_to_delete_idx = -1
                for i, debt in enumerate(debts):
                    if debt.get('message_id', -1) == 0 and str(replied_author_id) == debt.get('from_id') and debt.get('amount') == amount and debt.get('reason') == reason:
                        debt_to_delete_idx = i
                        deleted_info = f"Старый долг: {debt['from_name']} → {debt['to_name']} на {debt['amount']:.2f} лир"
                        break

                if debt_to_delete_idx != -1:
                    del chat_data[chat_id]['debts'][debt_to_delete_idx]
                    deleted = True
            except (ValueError, IndexError): pass

    if deleted:
        save_data()
        message.reply_text(f"✅ Запись удалена:\n`{deleted_info}`")
        update_summary_message(context.bot, chat_id)
    else:
        message.reply_text("Не нашел такой записи в базе. Возможно, это не сообщение о расходе/долге.")

def main() -> None:
    load_data()
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher

    if CHAT_ID_FOR_NOTIFICATIONS:
        try:
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            bot.send_message(chat_id=CHAT_ID_FOR_NOTIFICATIONS, text="✅ Бот запущен и снова в сети! (v1.3)")
            logger.info(f"Отправлено уведомление о запуске в чат {CHAT_ID_FOR_NOTIFICATIONS}")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление о запуске: {e}")

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("getchatid", get_chat_id))
    dispatcher.add_handler(CommandHandler("start_tracking", start_tracking))
    dispatcher.add_handler(CommandHandler("reset", reset_tracking))
    dispatcher.add_handler(CommandHandler("owe", owe))
    dispatcher.add_handler(CommandHandler("reset_debts", reset_debts))
    dispatcher.add_handler(CommandHandler("delete", delete_entry))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_expense))

    updater.start_polling(drop_pending_updates=False)
    logger.info("Бот запущен...")
    updater.idle()

if __name__ == '__main__':
    main()
