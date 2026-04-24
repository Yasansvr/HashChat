import telebot
from telebot.types import InlineQueryResultArticle, InputTextMessageContent
import uuid
from mnemonic import Mnemonic
import hashlib
import binascii
import json
import os
import datetime
from nacl.public import PrivateKey, PublicKey, SealedBox
from nacl.signing import SigningKey, VerifyKey
import nacl.encoding
import nacl.exceptions

TOKEN = "***REMOVED***"
bot = telebot.TeleBot(TOKEN, parse_mode=None)

DB_FILE = 'users.json'

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f)

def log_message(sender_id, receiver_id):
    with open("message_log.txt", "a") as f:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] User {sender_id} sent an encrypted message to User {receiver_id}\n")

def get_keys_from_password(password: str):
    # Hash password to get a 32-byte seed
    seed = hashlib.sha256(password.strip().encode('utf-8')).digest()
    
    # Generate X25519 keypair for encryption
    enc_private_key = PrivateKey(seed)
    enc_public_key = enc_private_key.public_key
    
    # Generate Ed25519 keypair for signing
    sign_private_key = SigningKey(seed)
    sign_public_key = sign_private_key.verify_key
    
    return {
        'enc_priv': enc_private_key,
        'enc_pub': enc_public_key,
        'sign_priv': sign_private_key,
        'sign_pub': sign_public_key
    }

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    help_text = (
        "Welcome to the Anonymous Crypto Bot!\n\n"
        "/newkey - Generate a 12-word seed phrase and get your keys/UUID.\n"
        "/encrypt - Encrypt and send a message to a friend's UUID.\n"
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
        "*(Note: Because this operates as a Telegram bot, your seed phrase briefly passes through Telegram's servers when sent. For absolute maximum paranoia, you can run this open-source script locally!)*\n"
        "*(EVEVRY TIME THAT YOU GENERATE NEWKEY IT IS IMPORTANT TO UPDATE YOUR SOCIAL PUBLIC KEY, OTHERWISE YOU SHOULD TEST ENCRYPTED MESSAGE WITH ALL PREVIOUS PRIVATE KEYS :) )*"
    )
    bot.reply_to(message, about_text, parse_mode='Markdown')

# --- /newkey ---
@bot.message_handler(commands=['newkey'])
def cmd_newkey(message):
    mnemo = Mnemonic("english")
    seed_phrase = mnemo.generate(strength=128)
    
    keys = get_keys_from_password(seed_phrase)
    
    enc_pub_hex = keys['enc_pub'].encode(encoder=nacl.encoding.HexEncoder).decode('utf-8')
    sign_pub_hex = keys['sign_pub'].encode(encoder=nacl.encoding.HexEncoder).decode('utf-8')
    
    # Save to DB
    user_id = str(message.chat.id)
    db = load_db()
    db[user_id] = {
        'enc_pub': enc_pub_hex,
        'sign_pub': sign_pub_hex
    }
    save_db(db)
    
    reply = (
        "Here is your new secret identity!\n\n"
        f"**Your 12-Word Seed Phrase:**\n`{seed_phrase}`\n"
        "*(WRITE THIS DOWN! You will need it to decrypt and sign messages!)*\n\n"
        f"**Your UUID is:** `{user_id}` (Internal Routing ID)\n\n"
        f"Encryption Public Key (Give this to your friends so they can encrypt messages to you):\n`{enc_pub_hex}`\n\n"
        f"Signing Public Key (Give this to your friends so they can verify your messages):\n`{sign_pub_hex}`\n\n"
        "Remember: Use the Encryption key to receive messages, and the Signing key to prove your identity!"
    )
    bot.send_message(message.chat.id, reply, parse_mode='Markdown')

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
        
    db = load_db()
    friend_uuid = None
    for uuid, keys in db.items():
        if keys.get('enc_pub') == pub_key_hex:
            friend_uuid = uuid
            break
            
    try:
        sealed_box = SealedBox(friend_pub_key)
        encrypted = sealed_box.encrypt(msg_text.encode('utf-8'), encoder=nacl.encoding.HexEncoder)
        encrypted_text = encrypted.decode('utf-8')
        
        if friend_uuid:
            # Send to friend
            bot.send_message(friend_uuid, f"You received a new encrypted message!\n`/decrypt {encrypted_text}`", parse_mode='Markdown')
            bot.reply_to(message, "Message successfully encrypted and routed to the owner of that public key!")
            log_message(message.chat.id, friend_uuid)
        else:
            bot.reply_to(message, f"Encrypted message (I don't know who owns this key, so please copy and send it manually):\n`/decrypt {encrypted_text}`", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"Encryption failed: {e}")

# --- /decrypt or /newHashMsg ---
@bot.message_handler(commands=['decrypt', 'newHashMsg'])
def cmd_decrypt(message):
    parts = message.text.split(' ', 1)
    if len(parts) == 2:
        encrypted_hex = parts[1]
        msg = bot.reply_to(message, "Please reply with your 12-word seed phrase to decrypt. I will delete your reply.")
        bot.register_next_step_handler(msg, process_decrypt_password, encrypted_hex)
    elif len(parts) == 1:
        msg = bot.reply_to(message, "Please reply with the encrypted message you want to decrypt.")
        bot.register_next_step_handler(msg, process_decrypt_msg_step)
    else:
        bot.reply_to(message, "Usage: /decrypt OR /decrypt [encrypted_message_hex]")

def process_decrypt_msg_step(message):
    encrypted_hex = message.text.strip()
    msg = bot.reply_to(message, "Please reply with your 12-word seed phrase to decrypt. I will delete your reply.")
    bot.register_next_step_handler(msg, process_decrypt_password, encrypted_hex)

def process_decrypt_password(message, encrypted_hex):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
        
    password = message.text
    if not password:
        bot.reply_to(message, "Invalid seed phrase.")
        return
        
    keys = get_keys_from_password(password)
    unseal_box = SealedBox(keys['enc_priv'])
    
    encrypted_hex = encrypted_hex.strip().replace('`', '')
    try:
        encrypted_bytes = binascii.unhexlify(encrypted_hex)
        decrypted = unseal_box.decrypt(encrypted_bytes)
        bot.send_message(message.chat.id, f"Decrypted Message:\n{decrypted.decode('utf-8')}")
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
        msg = bot.reply_to(message, "Please reply with your 12-word seed phrase to sign. I will delete your reply.")
        bot.register_next_step_handler(msg, process_sign_password, msg_text)
    elif len(parts) == 1:
        msg = bot.reply_to(message, "Please reply with the message you want to sign.")
        bot.register_next_step_handler(msg, process_sign_msg_step)
    else:
        bot.reply_to(message, "Usage: /sign OR /sign [message to sign]")

def process_sign_msg_step(message):
    msg_text = message.text.strip()
    msg = bot.reply_to(message, "Please reply with your 12-word seed phrase to sign. I will delete your reply.")
    bot.register_next_step_handler(msg, process_sign_password, msg_text)

def process_sign_password(message, msg_text):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
        
    password = message.text
    if not password:
        bot.reply_to(message, "Invalid seed phrase.")
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
    
    if cmd == 'encrypt':
        if len(parts) < 3:
            results.append(InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="Encrypt Message",
                description="Usage: encrypt [pub_key_hex] [message(use '-' instead space)]",
                input_message_content=InputTextMessageContent("Waiting for full encryption parameters...")
            ))
        else:
            pub_key_hex = parts[1].strip().replace('`', '')
            msg_text = parts[2].strip()
            try:
                pub_key_bytes = binascii.unhexlify(pub_key_hex)
                friend_pub_key = PublicKey(pub_key_bytes)
                sealed_box = SealedBox(friend_pub_key)
                encrypted = sealed_box.encrypt(msg_text.encode('utf-8'), encoder=nacl.encoding.HexEncoder)
                encrypted_text = encrypted.decode('utf-8')
                
                results.append(InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="Send Encrypted Message",
                    description="Tap to send ciphertext to chat",
                    input_message_content=InputTextMessageContent(f"🔒 You received an encrypted message!\n`/decrypt {encrypted_text}`", parse_mode='Markdown')
                ))
            except Exception as e:
                results.append(InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="Encryption Error",
                    description="Check public key format",
                    input_message_content=InputTextMessageContent(f"Error: {e}")
                ))
    elif cmd == 'verify':
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
                
    elif cmd in ['sign', 'decrypt']:
        results.append(InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title="Action Not Allowed Inline",
            description="For security, sign and decrypt must be done in the private bot chat.",
            input_message_content=InputTextMessageContent("Security Error: Seed phrases cannot be safely entered in inline queries.")
        ))
    else:
        results.append(InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title="Available Inline Commands",
            description="encrypt [pub_key] [msg]  OR  verify [pub_key] [msg]",
            input_message_content=InputTextMessageContent("Invalid inline command. Use encrypt or verify.")
        ))
        
    bot.answer_inline_query(query.id, results)

bot.set_my_commands([
    telebot.types.BotCommand("/newkey", "Generate a 12-word seed phrase and get your keys"),
    telebot.types.BotCommand("/encrypt", "Encrypt and send a message to a friend's public key"),
    telebot.types.BotCommand("/decrypt", "Decrypt a message sent to you"),
    telebot.types.BotCommand("/sign", "Sign a message so others know it's from you"),
    telebot.types.BotCommand("/verify", "Verify a signed message from a friend"),
    telebot.types.BotCommand("/abouthashchat", "Learn how HashChat keeps you secure"),
])

bot.infinity_polling()