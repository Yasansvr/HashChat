import telebot
from telebot.types import InlineQueryResultArticle, InputTextMessageContent
import uuid
from mnemonic import Mnemonic
import hashlib
import binascii
from nacl.public import PrivateKey, PublicKey, SealedBox
from nacl.signing import SigningKey, VerifyKey
from nacl.secret import SecretBox
import nacl.encoding
import nacl.exceptions
import nacl.pwhash
import nacl.utils

from bot_instance import bot
from database import load_db, save_db, load_messages, save_messages, db_transaction, messages_transaction
from crypto_utils import get_keys_from_password, get_seed_from_input

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "Welcome to the Anonymous Crypto ChatBot!\n\n"
        "This is an E2EE (End-to-End Encrypted) and\n"
        "open-source! So you can check the source code from github \n"
        "AND VERIFY IT VIA APP!\n"
        "For more information check /abouthashchat\n"
        "For generating new keys /newkey\n"
        "For any help /help\n\n"
        "Have fun and be Anonymous! "
    )
    bot.reply_to(message, welcome_text)

    db = load_db()
    has_key = False
    for sid, data in db.items():
        if sid == str(message.chat.id) or (isinstance(data, dict) and data.get('chat_id') == message.chat.id):
            has_key = True
            break

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = (
        "Welcome to the Anonymous Crypto Bot!\n\n"
        "/newkey - Generate a 12-word seed phrase and get your keys/ID.\n"
        "/delkey - Delete your active keys.\n"
        "/setpassword - Lock your 12-word seed phrase with a custom password.\n"
        "/encrypt - Encrypt and send a message to a friend's public key.\n"
        "/decrypt or /newHashMsg - Decrypt a message sent to you.\n"
        "/sign - Sign a message so others know it's from you.\n"
        "/verify - Verify a signed message from a friend.\n"
        "/abouthashchat - Learn about HashChat's security."
    )
    bot.reply_to(message, help_text)

# --- /aboutHashChat ---
@bot.message_handler(commands=['abouthashchat'])
def cmd_about(message):
    about_text = (
        "🔐 *About HashChat Security* 🔐\n\n"
        "HashChat uses military-grade cryptographic standards to ensure your messages remain truly private.\n\n"
        "*1. End-to-End Encryption (E2EE)*\n"
        "We use Curve25519 (via Libsodium/PyNaCl) for incredibly strong public-key encryption. When you encrypt a message for a friend, only their specific private key can decrypt it. Not even this bot or Telegram can read the message contents.\n\n"
        "*2. Seed Phrase Key Generation*\n"
        "Your keys are generated deterministically using a secure 12-word BIP39 seed phrase hashed with SHA-256. This means we **never** store your private keys. You hold the keys to your identity.\n\n"
        "*3. Digital Signatures*\n"
        "We use Ed25519 signatures. When you sign a message, anyone can mathematically verify that you (and only you) wrote it.\n\n"
        "*4. Privacy First*\n"
        "When you type your 12-word seed phrase to decrypt or sign, the bot instantly deletes your message from the chat history so it doesn't linger.\n\n"
        "⚠️ **CRITICAL SECURITY WARNING** ⚠️\n"
        "*(Because this operates as a Telegram bot, your seed phrase ALWAYS passes through Telegram's servers when sent in chat. Even though the bot deletes your message, Telegram may retain logs on their servers. For absolute maximum paranoia, you should NOT use seed phrases inside a standard Telegram chat. Instead, run this open-source script locally!)*\n"
    )
    bot.reply_to(message, about_text, parse_mode='Markdown')

# --- /newkey ---
@bot.message_handler(commands=['newkey'])
def cmd_newkey(message):
    db = load_db()
    
    # Check if user already has keys
    for sid, data in db.items():
        if sid == str(message.chat.id) or (isinstance(data, dict) and data.get('chat_id') == message.chat.id):
            bot.reply_to(message, "You already have active keys! Please delete them first using /delkey.")
            return

    mnemo = Mnemonic("english")
    seed_phrase = mnemo.generate(strength=128)
    
    keys = get_keys_from_password(seed_phrase)
    
    enc_pub_hex = keys['enc_pub'].encode(encoder=nacl.encoding.HexEncoder).decode('utf-8')
    sign_pub_hex = keys['sign_pub'].encode(encoder=nacl.encoding.HexEncoder).decode('utf-8')
    
    with db_transaction() as db:
        # Save to DB with short ID
        short_id = uuid.uuid4().hex[:8]
        while short_id in db:
            short_id = uuid.uuid4().hex[:8]
            
        db[short_id] = {
            'chat_id': message.chat.id,
            'enc_pub': enc_pub_hex,
            'sign_pub': sign_pub_hex
        }
    
    reply = (
        "Here is your new secret identity!\n\n"
        f"**Your 12-Word Seed Phrase:**\n`{seed_phrase}`\n"
        "*(WRITE THIS DOWN! You will need it to decrypt and sign messages!)*\n\n"
        f"Encryption Public Key (Give this to your friends so they can encrypt messages to you):\n`{enc_pub_hex}`\n\n"
        f"Signing Public Key (Give this to your friends so they can verify your messages):\n`{sign_pub_hex}`\n\n"
        "Remember: Use the Encryption key to receive messages, and the Signing key to prove your identity!"
    )
    bot.send_message(message.chat.id, reply, parse_mode='Markdown')

    markup = telebot.types.ForceReply(selective=True)
    msg = bot.send_message(message.chat.id, "Would you like to lock this seed phrase with a custom password so you don't have to re-type the 12 words later?\n\nIf yes, please reply with your new **custom password** (4+ chars). If no, just ignore this message.", reply_markup=markup)
    bot.register_next_step_handler(msg, process_setpassword_step2, short_id, seed_phrase)

# --- /setpassword ---
@bot.message_handler(commands=['setpassword'])
def cmd_setpassword(message):
    markup = telebot.types.ForceReply(selective=True)
    msg = bot.send_message(message.chat.id, "To lock your seed phrase with a custom password, please first reply with your 12-word seed phrase to verify ownership. I will delete your reply.", reply_markup=markup)
    bot.register_next_step_handler(msg, process_setpassword_step1)

def process_setpassword_step1(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass

    seed_phrase = message.text.strip() if message.text else ""
    if not seed_phrase:
        bot.send_message(message.chat.id, "Invalid seed phrase.")
        return

    try:
        keys = get_keys_from_password(seed_phrase)
        enc_pub_hex = keys['enc_pub'].encode(encoder=nacl.encoding.HexEncoder).decode('utf-8')
    except Exception:
        bot.send_message(message.chat.id, "Invalid seed phrase.")
        return

    db = load_db()
    user_sid = None
    for sid, data in db.items():
        if (sid == str(message.chat.id) or (isinstance(data, dict) and data.get('chat_id') == message.chat.id)) and (isinstance(data, dict) and data.get('enc_pub') == enc_pub_hex):
            user_sid = sid
            break

    if not user_sid:
        bot.send_message(message.chat.id, "Seed phrase does not match your active keys, or you don't have any active keys. Generate keys first with /newkey.")
        return

    markup = telebot.types.ForceReply(selective=True)
    msg = bot.send_message(message.chat.id, "Identity verified! Now, please reply with your new **custom password**. This password will be used to unlock your seed phrase for all future decryptions/signatures. I will delete your reply.", reply_markup=markup)
    bot.register_next_step_handler(msg, process_setpassword_step2, user_sid, seed_phrase)

def process_setpassword_step2(message, user_sid, seed_phrase):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass

    custom_password = message.text.strip() if message.text else ""
    if len(custom_password) < 4:
        bot.send_message(message.chat.id, "Password is too short. Please try /setpassword again with a stronger password.")
        return

    try:
        # Generate a random salt
        salt = nacl.utils.random(nacl.pwhash.argon2id.SALTBYTES)
        
        # Encrypt the seed phrase using the password
        password_hash = nacl.pwhash.argon2id.kdf(
            SecretBox.KEY_SIZE,
            custom_password.encode('utf-8'),
            salt,
            opslimit=nacl.pwhash.argon2id.OPSLIMIT_INTERACTIVE,
            memlimit=nacl.pwhash.argon2id.MEMLIMIT_INTERACTIVE
        )
        box = SecretBox(password_hash)
        encrypted = box.encrypt(seed_phrase.encode('utf-8'))
        encrypted_hex = binascii.hexlify(encrypted).decode('utf-8')
        salt_hex = binascii.hexlify(salt).decode('utf-8')

        # Save to DB
        with db_transaction() as db:
            if user_sid in db and isinstance(db[user_sid], dict):
                db[user_sid]['encrypted_seed'] = encrypted_hex
                db[user_sid]['password_salt'] = salt_hex
                bot.send_message(message.chat.id, "✅ Success! Your 12-word seed phrase is now securely encrypted and locked behind your custom password on this server.\n\nFrom now on, when the bot asks for your seed phrase, you can just reply with your custom password!")
            else:
                bot.send_message(message.chat.id, "Error: User not found in database during save.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Encryption error: {e}")


# --- /delkey ---
@bot.message_handler(commands=['delkey'])
def cmd_delkey(message):
    msg = bot.reply_to(message, "Please reply with your custom password OR your 12-word seed phrase to confirm deletion of your keys. I will delete your reply.")
    bot.register_next_step_handler(msg, process_delkey_password)

def process_delkey_password(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
        
    password = get_seed_from_input(message.chat.id, message.text)
    if not password:
        bot.send_message(message.chat.id, "Invalid seed phrase/password.")
        return
        
    try:
        keys = get_keys_from_password(password)
        enc_pub_hex = keys['enc_pub'].encode(encoder=nacl.encoding.HexEncoder).decode('utf-8')
    except Exception:
        bot.send_message(message.chat.id, "Invalid seed phrase.")
        return

    with db_transaction() as db:
        to_delete = None
        for sid, data in db.items():
            if (sid == str(message.chat.id) or (isinstance(data, dict) and data.get('chat_id') == message.chat.id)) and (isinstance(data, dict) and data.get('enc_pub') == enc_pub_hex):
                to_delete = sid
                break
                
        if to_delete:
            del db[to_delete]
            bot.send_message(message.chat.id, "✅ Your keys and Routing ID have been permanently deleted from the database. You are no longer registered.\n\nYou can generate new keys anytime using /newkey.")
        else:
            bot.send_message(message.chat.id, "Seed phrase does not match your active keys, or you don't have any active keys.")

# --- /encrypt ---
@bot.message_handler(commands=['encrypt'])
def cmd_encrypt(message):
    parts = message.text.split(' ', 2)
    if len(parts) == 3:
        process_encrypt_final(message, parts[1], parts[2])
    elif len(parts) == 1:
        msg = bot.reply_to(message, "Please reply with your friend's encryption public key.")
        bot.register_next_step_handler(msg, process_encrypt_pub_key_step)
    else:
        bot.reply_to(message, "Usage: /encrypt OR /encrypt [friend_encryption_public_key] [message]")

def process_encrypt_pub_key_step(message):
    pub_key_hex = message.text.strip()
    msg = bot.reply_to(message, "Great! Now reply with the message you want to encrypt.")
    bot.register_next_step_handler(msg, process_encrypt_message_step, pub_key_hex)

def process_encrypt_message_step(message, pub_key_hex):
    msg_text = message.text.strip()
    process_encrypt_final(message, pub_key_hex, msg_text)

def process_encrypt_final(message, pub_key_hex, msg_text):
    pub_key_hex = pub_key_hex.strip().replace('`', '')
    try:
        pub_key_bytes = binascii.unhexlify(pub_key_hex)
        friend_pub_key = PublicKey(pub_key_bytes)
    except Exception:
        bot.reply_to(message, "Invalid public key format. Please provide a valid hex string.")
        return
        
    try:
        sealed_box = SealedBox(friend_pub_key)
        encrypted = sealed_box.encrypt(msg_text.encode('utf-8'), encoder=nacl.encoding.HexEncoder)
        encrypted_text = encrypted.decode('utf-8')
        
        # Try to find friend's chat ID to notify them directly
        db = load_db()
        friend_chat_id = None
        for sid, keys in db.items():
            if isinstance(keys, dict) and keys.get('enc_pub') == pub_key_hex:
                friend_chat_id = keys.get('chat_id')
                break
                
        # Generate a unique short ID for the message
        with messages_transaction() as msg_db:
            msg_id = uuid.uuid4().hex[:8]
            while msg_id in msg_db:
                msg_id = uuid.uuid4().hex[:8]
                
            msg_db[msg_id] = {
                'ciphertext': encrypted_text,
                'sender_chat_id': message.chat.id,
                'friend_chat_id': friend_chat_id
            }
                
        if friend_chat_id:
            # Send to friend
            bot.send_message(friend_chat_id, f"🔒 You received a new encrypted message!\n\n/decrypt", parse_mode='Markdown')
            bot.reply_to(message, "Message successfully encrypted and routed to the owner of that public key!")
        else:
            bot.reply_to(message, f"Encrypted message (I don't know who owns this key, so please copy and send it manually):\n\n`{encrypted_text}`\n\n/decrypt", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"Encryption failed: {e}")

# --- /decrypt or /newHashMsg ---
@bot.message_handler(commands=['decrypt'])
def cmd_decrypt(message):
    text = message.text.strip()
    
    parts = text.split(' ', 1)
    if len(parts) == 2:
        encrypted_hex = parts[1]
        msg = bot.reply_to(message, "🔑Please reply with your custom password OR your 12-word seed phrase to decrypt. I will delete your reply.")
        bot.register_next_step_handler(msg, process_decrypt_password, encrypted_hex)
    elif len(parts) == 1:
        messages_db = load_messages()
        user_chat_id = message.chat.id
        
        pending_messages = []
        for msg_id, val in messages_db.items():
            if isinstance(val, dict) and val.get('friend_chat_id') == user_chat_id:
                pending_messages.append(msg_id)
                
        if not pending_messages:
            msg = bot.reply_to(message, "You have no pending messages. Please reply with the encrypted message you want to decrypt.")
            bot.register_next_step_handler(msg, process_decrypt_msg_step)
            return
            
        markup = telebot.types.InlineKeyboardMarkup()
        for msg_id in pending_messages:
            markup.add(telebot.types.InlineKeyboardButton(text=f"ID: {msg_id}", callback_data=f"dec_{msg_id}"))
            
        bot.reply_to(message, "Select a pending message to decrypt:", reply_markup=markup)
    else:
        bot.reply_to(message, "Usage: /decrypt OR /decrypt [encrypted_message_hex]")

@bot.callback_query_handler(func=lambda call: call.data.startswith('dec_'))
def callback_decrypt(call):
    msg_id = call.data.split('_')[1]
    
    messages_db = load_messages()
    if msg_id in messages_db:
        val = messages_db[msg_id]
        encrypted_hex = val.get('ciphertext') if isinstance(val, dict) else val
        msg = bot.send_message(call.message.chat.id, f"🔑 Decrypting Message {msg_id}.\nPlease reply with your custom password OR your 12-word seed phrase. I will delete your reply.")
        bot.register_next_step_handler(msg, process_decrypt_password, encrypted_hex)
    else:
        bot.send_message(call.message.chat.id, "Message not found in database.")
    bot.answer_callback_query(call.id)

def process_decrypt_msg_step(message):
    encrypted_hex = message.text.strip()
        
    msg = bot.reply_to(message, "Please reply with your custom password OR your 12-word seed phrase to decrypt. I will delete your reply.")
    bot.register_next_step_handler(msg, process_decrypt_password, encrypted_hex)

def process_decrypt_password(message, encrypted_hex):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
        
    password = get_seed_from_input(message.chat.id, message.text)
    if not password:
        bot.send_message(message.chat.id, "Invalid seed phrase/password.")
        return
        
    keys = get_keys_from_password(password)
    unseal_box = SealedBox(keys['enc_priv'])
    
    encrypted_hex = encrypted_hex.strip().replace('`', '')
    try:
        encrypted_bytes = binascii.unhexlify(encrypted_hex)
        decrypted = unseal_box.decrypt(encrypted_bytes)
        bot.send_message(message.chat.id, f"📭Decrypted Message:\n{decrypted.decode('utf-8')}")
        
        # Auto-delete from DB
        with messages_transaction() as messages_db:
            for key, val in list(messages_db.items()):
                actual_cipher = val.get('ciphertext') if isinstance(val, dict) else val
                if actual_cipher == encrypted_hex:
                    del messages_db[key]
            
    except nacl.exceptions.CryptoError:
        bot.send_message(message.chat.id, "Decryption failed! Wrong seed phrase or corrupted message.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {e}")

# --- /sign ---
@bot.message_handler(commands=['sign'])
def cmd_sign(message):
    parts = message.text.split(' ', 1)
    if len(parts) == 2:
        msg_text = parts[1]
        msg = bot.reply_to(message, "Please reply with your custom password OR your 12-word seed phrase to sign. I will delete your reply.")
        bot.register_next_step_handler(msg, process_sign_password, msg_text)
    elif len(parts) == 1:
        msg = bot.reply_to(message, "Please reply with the message you want to sign.")
        bot.register_next_step_handler(msg, process_sign_msg_step)
    else:
        bot.reply_to(message, "Usage: /sign OR /sign [message to sign]")

def process_sign_msg_step(message):
    msg_text = message.text.strip()
    msg = bot.reply_to(message, "Please reply with your custom password OR your 12-word seed phrase to sign. I will delete your reply.")
    bot.register_next_step_handler(msg, process_sign_password, msg_text)

def process_sign_password(message, msg_text):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
        
    password = get_seed_from_input(message.chat.id, message.text)
    if not password:
        bot.send_message(message.chat.id, "Invalid seed phrase/password.")
        return
        
    keys = get_keys_from_password(password)
    signing_key = keys['sign_priv']
    
    try:
        signed = signing_key.sign(msg_text.encode('utf-8'), encoder=nacl.encoding.HexEncoder)
        bot.send_message(message.chat.id, f"Signed Message (copy this entire string):\n`{signed.decode('utf-8')}`", parse_mode='Markdown')
    except Exception as e:
        bot.send_message(message.chat.id, f"Signing failed: {e}")

# --- /verify ---
@bot.message_handler(commands=['verify'])
def cmd_verify(message):
    parts = message.text.split(' ', 2)
    if len(parts) == 3:
        process_verify_final(message, parts[1], parts[2])
    elif len(parts) == 1:
        msg = bot.reply_to(message, "Please reply with your friend's signing public key.")
        bot.register_next_step_handler(msg, process_verify_pub_key_step)
    else:
        bot.reply_to(message, "Usage: /verify OR /verify [friend_signing_public_key] [signed_message_hex]")

def process_verify_pub_key_step(message):
    pub_key_hex = message.text.strip()
    msg = bot.reply_to(message, "Great! Now reply with the signed message you want to verify.")
    bot.register_next_step_handler(msg, process_verify_msg_step, pub_key_hex)

def process_verify_msg_step(message, pub_key_hex):
    signed_hex = message.text.strip()
    process_verify_final(message, pub_key_hex, signed_hex)

def process_verify_final(message, pub_key_hex, signed_hex):
    pub_key_hex = pub_key_hex.strip().replace('`', '')
    signed_hex = signed_hex.strip().replace('`', '')
    
    try:
        pub_key_bytes = binascii.unhexlify(pub_key_hex)
        verify_key = VerifyKey(pub_key_bytes)
    except Exception:
        bot.reply_to(message, "Invalid public key format. Please provide a valid hex string.")
        return
        
    try:
        signed_bytes = binascii.unhexlify(signed_hex)
        message_bytes = verify_key.verify(signed_bytes)
        bot.reply_to(message, f"Signature is VALID! The message is:\n{message_bytes.decode('utf-8')}")
    except nacl.exceptions.BadSignatureError:
        bot.reply_to(message, "Signature is INVALID! The message was tampered with, or you used the wrong public key (e.g., using the Encryption key instead of the Signing key).")
    except Exception as e:
        bot.reply_to(message, f"Verification failed: {e}")

# --- Inline Query Handler ---
@bot.inline_handler(lambda query: len(query.query) > 0)
def query_text(query):
    parts = query.query.strip().split(' ', 2)
    cmd = parts[0].lower()
    
    results = []
    
    if cmd == 'verify':
        if len(parts) < 3:
            results.append(InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="Verify Message",
                description="Usage: verify [signing_pub_key] [signed_message_hex]",
                input_message_content=InputTextMessageContent("Waiting for full verification parameters...")
            ))
        else:
            pub_key_hex = parts[1].strip().replace('`', '')
            signed_hex = parts[2].strip().replace('`', '')
            try:
                pub_key_bytes = binascii.unhexlify(pub_key_hex)
                verify_key = VerifyKey(pub_key_bytes)
                signed_bytes = binascii.unhexlify(signed_hex)
                message_bytes = verify_key.verify(signed_bytes)
                
                results.append(InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="Valid Signature!",
                    description="Tap to send verification result",
                    input_message_content=InputTextMessageContent(f"✅ Signature is VALID! The message is:\n{message_bytes.decode('utf-8')}")
                ))
            except nacl.exceptions.BadSignatureError:
                results.append(InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="INVALID Signature",
                    description="Tap to send verification result",
                    input_message_content=InputTextMessageContent("❌ Signature is INVALID! The message was tampered with or the wrong key was used.")
                ))
            except Exception as e:
                pass
                
    elif cmd in ['sign', 'decrypt', 'encrypt']:
        results.append(InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title="Action Not Allowed Inline",
            description="For security, encrypt, sign and decrypt must be done in the private bot chat.",
            input_message_content=InputTextMessageContent("Security Error: Seed phrases and plaintext cannot be safely entered in inline queries.")
        ))
    else:
        results.append(InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title="Available Inline Commands",
            description="verify [pub_key] [msg]",
            input_message_content=InputTextMessageContent("Invalid inline command. Use verify.")
        ))
        
    bot.answer_inline_query(query.id, results)
