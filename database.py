import json
import os
import threading
import contextlib
from config import DB_FILE, MESSAGES_FILE

db_lock = threading.Lock()
messages_lock = threading.Lock()

def load_db():
    with db_lock:
        if os.path.exists(DB_FILE) and os.path.getsize(DB_FILE) > 0:
            try:
                with open(DB_FILE, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

def save_db(db):
    with db_lock:
        with open(DB_FILE, 'w') as f:
            json.dump(db, f)

@contextlib.contextmanager
def db_transaction():
    with db_lock:
        if os.path.exists(DB_FILE) and os.path.getsize(DB_FILE) > 0:
            try:
                with open(DB_FILE, 'r') as f:
                    db = json.load(f)
            except json.JSONDecodeError:
                db = {}
        else:
            db = {}
        yield db
        with open(DB_FILE, 'w') as f:
            json.dump(db, f)

def load_messages():
    with messages_lock:
        if os.path.exists(MESSAGES_FILE) and os.path.getsize(MESSAGES_FILE) > 0:
            try:
                with open(MESSAGES_FILE, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

def save_messages(db):
    with messages_lock:
        with open(MESSAGES_FILE, 'w') as f:
            json.dump(db, f)

@contextlib.contextmanager
def messages_transaction():
    with messages_lock:
        if os.path.exists(MESSAGES_FILE) and os.path.getsize(MESSAGES_FILE) > 0:
            try:
                with open(MESSAGES_FILE, 'r') as f:
                    db = json.load(f)
            except json.JSONDecodeError:
                db = {}
        else:
            db = {}
        yield db
        with open(MESSAGES_FILE, 'w') as f:
            json.dump(db, f)
