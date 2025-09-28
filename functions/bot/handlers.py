import logging
from telegram import Update, ParseMode, Bot
from telegram.error import BadRequest
from telegram.ext import CallbackContext
from .database import (
    add_or_update_user, get_chat_info, start_chat_tracking, 
    add_expense, add_debt, delete_entry,
    get_all_expenses, get_all_debts, get_user_names
)

logger = logging.getLogger(__name__)

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        'Привет! Я бот для учета расходов (v2.1).\n\n'
        'Добавьте меня в ваш групповой чат, сделайте администратором (нужно для закрепления сообщений) и отправьте команду ```/start_tracking``` чтобы начать.',
        parse_mode=ParseMode.MARKDOWN
    )

def ping(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Pong! Я в сети и готов к работе.")

def get_chat_id(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    update.message.reply_text(f"ID этого чата: `{chat_id}`")

def start_tracking(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    if get_chat_info(chat_id):
        update.message.reply_text('Учет расходов в этом чате уже ведется.')
        return

    message_text = '📊 **Учет общих расходов**\n\nРасходы пока не заведены.'
    sent_message = update.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN)
    try:
        context.bot.pin_chat_message(chat_id, sent_message.message_id)
        start_chat_tracking(chat_id, sent_message.message_id)
        logger.info(f"Начат учет в чате {chat_id}")
    except BadRequest:
        update.message.reply_text('Не удалось закрепить сообщение. Сделайте меня администратором.')

def owe(update: Update, context: CallbackContext) -> None:
    message = update.message
    if not get_chat_info(message.chat_id):
        return # Silently ignore

    if not message.reply_to_message:
        message.reply_text("Ошибка: нужно ответить на сообщение того, кому вы должны.")
        return

    try:
        debtor = message.from_user
        creditor = message.reply_to_message.from_user
        
        add_or_update_user(debtor.id, debtor.first_name)
        add_or_update_user(creditor.id, creditor.first_name)

        amount = float(context.args[0].replace(',', '.'))
        reason = ' '.join(context.args[1:]) if len(context.args) > 1 else 'Без описания'

        add_debt(message.chat_id, debtor.id, creditor.id, amount, reason, message.message_id)

        message.reply_text(f"✅ Записан долг: {debtor.first_name} должен(на) {creditor.first_name} {amount:.2f} лир ({reason}).")
        update_summary_message(context.bot, message.chat_id)

    except (IndexError, ValueError):
        message.reply_text("Неверный формат. Используйте: /owe <сумма> <описание>")
    except Exception as e:
        logger.error(f"Ошибка в команде /owe: {e}")
        message.reply_text("Произошла ошибка при записи долга.")

def handle_expense(update: Update, context: CallbackContext) -> None:
    message = update.message
    if not get_chat_info(message.chat_id):
        return

    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2: return
        
        amount = float(parts[0].replace(',', '.'))
        if amount <= 0: return
        
        description = parts[1]
        user = message.from_user

        add_or_update_user(user.id, user.first_name)
        add_expense(message.chat_id, user.id, amount, description, message.message_id)

        reply_text = f"✅ Записал расход: {amount:.2f} за '{description}' от {user.first_name}."
        message.reply_text(reply_text, parse_mode=ParseMode.MARKDOWN)
        
        update_summary_message(context.bot, message.chat_id)

    except (ValueError, IndexError):
        pass
    except Exception as e:
        logger.error(f"Непредвиденная ошибка в handle_expense: {e}", exc_info=True)

def delete_entry(update: Update, context: CallbackContext) -> None:
    message = update.message
    if not get_chat_info(message.chat_id):
        return

    if not message.reply_to_message:
        message.reply_text("Чтобы удалить запись, нужно ответить на нее командой /delete")
        return

    reply_to_id = message.reply_to_message.message_id
    deleted_type = delete_entry(message.chat_id, reply_to_id)

    if deleted_type == 'expense':
        deleted_info = "Расход удален."
    elif deleted_type == 'debt':
        deleted_info = "Долг удален."
    else:
        deleted_info = "Не нашел такой записи в базе."

    message.reply_text(f"✅ {deleted_info}")
    if deleted_info != "Не нашел такой записи в базе.":
        update_summary_message(context.bot, message.chat_id)

def update_summary_message(bot: Bot, chat_id: int) -> None:
    chat_info = get_chat_info(chat_id)
    if not chat_info:
        return

    summary_message_id = chat_info['message_id']
    all_expenses = get_all_expenses(chat_id)
    all_debts = get_all_debts(chat_id)

    user_ids = set()
    for exp in all_expenses:
        user_ids.add(exp['user_id'])
    for debt in all_debts:
        user_ids.add(debt['from_user_id'])
        user_ids.add(debt['to_user_id'])

    user_names = get_user_names(list(user_ids))
    user_totals = {uid: 0.0 for uid in user_ids}
    final_balances = {uid: 0.0 for uid in user_ids}

    for exp in all_expenses:
        user_totals[exp['user_id']] += exp['amount']

    summary_lines = []
    if all_expenses:
        summary_lines.append("*Детализация расходов:*")
        sorted_expenses = sorted(all_expenses, key=lambda x: x.get('timestamp', 0), reverse=True)
        for expense in sorted_expenses:
            user_name = user_names.get(str(expense['user_id']), 'Unknown')
            summary_lines.append(f"  - {expense['amount']:.2f} ({user_name}): {expense['description']}")
        summary_lines.append("")

    if any(v > 0 for v in user_totals.values()):
        total_spent = sum(user_totals.values())
        num_users_in_expenses = len(set(exp['user_id'] for exp in all_expenses))
        average_spent = total_spent / num_users_in_expenses if num_users_in_expenses > 0 else 0

        summary_lines.append("*Общие расходы:*")
        for user_id, total in user_totals.items():
            if total > 0:
                final_balances[user_id] = total - average_spent
                summary_lines.append(f"  - {user_names.get(str(user_id), 'Unknown')}: {total:.2f} лир")
        summary_lines.extend([f"\n*Всего потрачено:* {total_spent:.2f} лир", f"*Средний расход:* {average_spent:.2f} лир"])

    if all_debts:
        summary_lines.append("\n*Личные долги:*")
        for debt in all_debts:
            from_name = user_names.get(str(debt['from_user_id']), 'Unknown')
            to_name = user_names.get(str(debt['to_user_id']), 'Unknown')
            summary_lines.append(f"  - {from_name} → {to_name}: {debt['amount']:.2f} лир ({debt['reason']})")
            final_balances[debt['from_user_id']] -= debt['amount']
            final_balances[debt['to_user_id']] += debt['amount']

    if final_balances:
        summary_lines.append("\n*ИТОГОВЫЙ БАЛАНС:*")
        balances_list = [{'name': user_names.get(str(uid), f'User {uid}'), 'balance': bal} for uid, bal in final_balances.items()]
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

    final_text = '📊 **Учет общих расходов**\n\n' + ('Расходы пока не заведены.' if not summary_lines else '\n'.join(summary_lines))

    if len(final_text) > 4096:
        final_text = final_text[:4090] + "..."

    try:
        bot.edit_message_text(chat_id=chat_id, message_id=summary_message_id, text=final_text, parse_mode=ParseMode.MARKDOWN)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            logger.error(f"Ошибка BadRequest при обновлении сообщения: {e}")
