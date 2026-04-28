import os
import sys

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    print("ERROR: BOT_TOKEN environment variable not set. Please export BOT_TOKEN='your_token'")
    sys.exit(1)

DB_FILE = 'users.json'
MESSAGES_FILE = 'messages.json'
