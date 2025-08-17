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
        'Привет! Я бот для учета расходов.\n\n'
        '✅ *Общие расходы*: `сумма описание`\n'
        '   (например: `1500 продукты`)\n\n'
        '✅ *Личный долг*: Ответьте на сообщение человека, '
        'которому вы должны, и напишите:\n'
        '`/owe сумма описание`\n'
        '   (например: `/owe 1000 подарок`)\n\n'
        'Другие команды:\n'
        '/start_tracking - Начать учет в чате\n'
        '/reset - Полностью сбросить все расходы\n'
        '/reset_debts - Сбросить только личные долги\n'
        '/getchatid - Узнать ID этого чата',
        parse_mode=ParseMode.MARKDOWN
    )
def get_chat_id(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    update.message.reply_text(f"ID этого чата: `{chat_id}`\n\nСкопируйте это число и добавьте в .env файл.")
def start_tracking(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    if chat_id in chat_data:
        update.message.reply_text('Учет расходов в этом чате уже ведется.')
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
    if not update.message.reply_to_message:
        update.message.reply_text("Ошибка: нужно ответить на сообщение того, кому вы должны.")
        return
    chat_id = update.message.chat_id
    if chat_id not in chat_data:
        update.message.reply_text("Сначала начните учет командой /start_tracking")
        return
    try:
        debtor, creditor = update.message.from_user, update.message.reply_to_message.from_user
        if debtor.id == creditor.id:
            update.message.reply_text("Нельзя быть должным самому себе.")
            return
        amount = float(context.args[0].replace(',', '.'))
        reason = ' '.join(context.args[1:]) if len(context.args) > 1 else 'Без описания'
        if amount <= 0:
            update.message.reply_text("Сумма должна быть > 0.")
            return
        debt_record = {'from_id': str(debtor.id), 'from_name': debtor.first_name, 'to_id': str(creditor.id), 'to_name': creditor.first_name, 'amount': amount, 'reason': reason}
        chat_data[chat_id].setdefault('debts', []).append(debt_record)
        save_data()
        update.message.reply_text(f"✅ Записан долг: {debtor.first_name} должен(на) {creditor.first_name} {amount:.2f} лир ({reason}).")
        update_summary_message(context.bot, chat_id)
    except (IndexError, ValueError):
        update.message.reply_text("Неверный формат. Используйте: /owe <сумма> <описание>")
    except TimedOut:
        logger.warning("Произошел тайм-аут. Telegram должен повторить отправку.")
        pass
    except Exception as e:
        logger.error(f"Ошибка в команде /owe: {e}")
        update.message.reply_text("Произошла непредвиденная ошибка при записи долга.")
def update_summary_message(bot: Bot, chat_id: int) -> None:
    if chat_id not in chat_data: return
    data = chat_data[chat_id]
    users_data = {int(k): v for k, v in data.get('users', {}).items()}
    debts_data = data.get('debts', [])
    summary_lines, final_balances = [], {}
    if users_data:
        total_spent = sum(user['total'] for user in users_data.values())
        num_users = len(users_data)
        average_spent = total_spent / num_users if num_users > 0 else 0
        summary_lines.append("*Общие расходы:*")
        for user_id, user_info in users_data.items():
            final_balances[user_id] = user_info['total'] - average_spent
            summary_lines.append(f"  - {user_info['name']}: {user_info['total']:.2f} лир")
        summary_lines.extend([f"\n*Всего потрачено:* {total_spent:.2f} лир", f"*Средний расход:* {average_spent:.2f} лир"])
    if debts_data:
        summary_lines.append("\n*Личные долги:*")
        for debt in debts_data:
            from_id, to_id = int(debt['from_id']), int(debt['to_id'])
            summary_lines.append(f"  - {debt['from_name']} → {debt['to_name']}: {debt['amount']:.2f} лир ({debt['reason']})")
            final_balances[from_id] = final_balances.get(from_id, 0) - debt['amount']
            final_balances[to_id] = final_balances.get(to_id, 0) + debt['amount']
    if final_balances:
        summary_lines.append("\n*ИТОГОВЫЙ БАЛАНС:*")
        user_names = {u_id: u_info['name'] for u_id, u_info in users_data.items()}
        for debt in debts_data:
            user_names.setdefault(int(debt['from_id']), debt['from_name'])
            user_names.setdefault(int(debt['to_id']), debt['to_name'])
        balances_list = [{'name': user_names.get(uid, f'User {uid}'), 'balance': bal} for uid, bal in final_balances.items()]
        positive = sorted([b for b in balances_list if b['balance'] > 0], key=lambda x: x['balance'], reverse=True)
        negative = sorted([b for b in balances_list if b['balance'] < 0], key=lambda x: x['balance'])
        i, j = 0, 0
        while i < len(negative) and j < len(positive):
            debtor, creditor = negative[i], positive[j]
            amount = min(-debtor['balance'], creditor['balance'])
            if amount < 0.01: break
            summary_lines.append(f"  - {debtor['name']} должен(на) {creditor['name']}: {amount:.2f} лир")
            debtor['balance'] += amount
            creditor['balance'] -= amount
            if round(debtor['balance'], 2) == 0: i += 1
            if round(creditor['balance'], 2) == 0: j += 1
    final_text = '📊 **Учет общих расходов**\n\n' + ('Расходы пока не заведены.' if not summary_lines else '```\n' + '\n'.join(summary_lines) + '\n```')
    try:
        bot.edit_message_text(chat_id=chat_id, message_id=data['message_id'], text=final_text, parse_mode=ParseMode.MARKDOWN_V2)
    except BadRequest: pass
def handle_expense(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    if chat_id not in chat_data: return
    try:
        parts = update.message.text.split(maxsplit=1)
        if len(parts) < 2: return
        amount = float(parts[0].replace(',', '.'))
        if amount <= 0: return
        user = update.message.from_user
        user_id_str = str(user.id)
        users = chat_data[chat_id].setdefault('users', {})
        if user_id_str not in users:
            users[user_id_str] = {'name': user.first_name, 'total': 0.0}
        users[user_id_str]['total'] += amount
        save_data()
        logger.info(f"Добавлен общий расход {amount} от {user.first_name} в чате {chat_id}")
        update_summary_message(context.bot, chat_id)
    except (ValueError, IndexError):
        pass
    except TimedOut:
        logger.warning("Произошел тайм-аут при обработке расхода. Ждем повтора.")
        pass

def main() -> None:
    load_data()
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher

    if CHAT_ID_FOR_NOTIFICATIONS:
        try:
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            bot.send_message(chat_id=CHAT_ID_FOR_NOTIFICATIONS, text="✅ Бот запущен и снова в сети!")
            logger.info(f"Отправлено уведомление о запуске в чат {CHAT_ID_FOR_NOTIFICATIONS}")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление о запуске: {e}")
    else:
        logger.warning("Переменная CHAT_ID_FOR_NOTIFICATIONS не задана в .env. Уведомление о запуске не будет отправлено.")

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("getchatid", get_chat_id))
    dispatcher.add_handler(CommandHandler("start_tracking", start_tracking))
    dispatcher.add_handler(CommandHandler("reset", reset_tracking))
    dispatcher.add_handler(CommandHandler("owe", owe))
    dispatcher.add_handler(CommandHandler("reset_debts", reset_debts))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_expense))

    updater.start_polling(drop_pending_updates=False)
    logger.info("Бот запущен и готов обрабатывать пропущенные сообщения...")
    updater.idle()

if __name__ == '__main__':
    main()
