import firebase_admin
from firebase_admin import credentials, firestore
import logging
from .config import FIREBASE_CREDENTIALS

logger = logging.getLogger(__name__)

db = None

def initialize_firebase():
    """
    Initializes the Firebase Admin SDK and the Firestore client.
    """ 
    global db
    try:
        # Check if the app is already initialized
        if not firebase_admin._apps:
            cred = credentials.Certificate(FIREBASE_CREDENTIALS)
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            logger.info("Firebase-подключение успешно инициализировано.")
        else:
            db = firestore.client()
            logger.info("Firebase уже был инициализирован.")
    except Exception as e:
        logger.error(f"Ошибка при инициализации Firebase: {e}")
        raise

def add_or_update_user(user_id, name):
    """
    Adds a new user or updates an existing user's name in Firestore.
    """
    if not db:
        logger.error("Firestore клиент не инициализирован.")
        return

    try:
        user_ref = db.collection('users').document(str(user_id))
        user_ref.set({
            'name': name
        }, merge=True)
        logger.info(f"Пользователь {name} (ID: {user_id}) добавлен или обновлен в Firestore.")
    except Exception as e:
        logger.error(f"Ошибка при добавлении/обновлении пользователя {user_id}: {e}")

def get_chat_info(chat_id):
    """
    Retrieves tracking info for a given chat_id from Firestore.
    """
    if not db:
        return None
    chat_ref = db.collection('chats').document(str(chat_id))
    doc = chat_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

def start_chat_tracking(chat_id, message_id):
    """
    Starts tracking a chat by storing its message_id in Firestore.
    """
    if not db:
        return
    chat_ref = db.collection('chats').document(str(chat_id))
    chat_ref.set({
        'message_id': message_id
    })

def add_expense(chat_id, user_id, amount, description, message_id):
    """
    Adds an expense record to a chat's subcollection in Firestore.
    """
    if not db:
        return
    expense_data = {
        'user_id': user_id,
        'amount': amount,
        'description': description,
        'timestamp': firestore.SERVER_TIMESTAMP
    }
    db.collection('chats').document(str(chat_id)).collection('expenses').document(str(message_id)).set(expense_data)

def add_debt(chat_id, from_user_id, to_user_id, amount, reason, message_id):
    """
    Adds a debt record to a chat's subcollection in Firestore.
    """
    if not db:
        return
    debt_data = {
        'from_user_id': from_user_id,
        'to_user_id': to_user_id,
        'amount': amount,
        'reason': reason,
        'timestamp': firestore.SERVER_TIMESTAMP
    }
    db.collection('chats').document(str(chat_id)).collection('debts').document(str(message_id)).set(debt_data)

def delete_entry(chat_id, message_id):
    """
    Deletes an entry (expense or debt) from Firestore.
    Returns 'expense', 'debt', or None.
    """
    if not db:
        return None
    
    chat_id_str = str(chat_id)
    message_id_str = str(message_id)

    expense_ref = db.collection('chats').document(chat_id_str).collection('expenses').document(message_id_str)
    if expense_ref.get().exists:
        expense_ref.delete()
        return 'expense'

    debt_ref = db.collection('chats').document(chat_id_str).collection('debts').document(message_id_str)
    if debt_ref.get().exists:
        debt_ref.delete()
        return 'debt'

    return None

def get_all_expenses(chat_id):
    """Fetches all expenses for a chat."""
    if not db: return []
    expenses_ref = db.collection('chats').document(str(chat_id)).collection('expenses').stream()
    return [doc.to_dict() for doc in expenses_ref]

def get_all_debts(chat_id):
    """Fetches all debts for a chat."""
    if not db: return []
    debts_ref = db.collection('chats').document(str(chat_id)).collection('debts').stream()
    return [doc.to_dict() for doc in debts_ref]

def get_user_names(user_ids):
    """Fetches names for a list of user IDs."""
    if not db or not user_ids: return {}
    user_refs = [db.collection('users').document(str(uid)) for uid in user_ids]
    users = db.get_all(user_refs)
    return {user.id: user.to_dict()['name'] for user in users if user.exists}