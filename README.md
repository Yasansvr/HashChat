# HashChat

HashChat is an End-to-End Encrypted (E2EE) and anonymous Telegram Bot. It uses military-grade cryptographic standards (Curve25519 for encryption and Ed25519 for digital signatures via PyNaCl) to ensure your messages remain truly private. Your keys are generated deterministically using a secure 12-word BIP39 seed phrase. 

Features:
- **E2E Encryption**: Only the recipient with the matching private key can decrypt your messages.
- **Digital Signatures**: Sign messages to prove your identity mathematically.
- **Seed Phrase & Custom Passwords**: Keys are generated from a 12-word seed phrase, which you can securely lock behind a custom password.
- **Short Routing IDs**: Anonymous ID system to route messages to the correct user.

## Verifying Project Authenticity

To ensure that the code you are running is authentic and hasn't been tampered with, you can verify the cryptographic signatures of the commits or release archives using the author's public GPG key included in this repository.

### 1. Import the Public Key
First, import the provided `lsinxl.asc` key into your local GPG keychain:
```bash
gpg --import lsinxl.asc
```

### 2. Verify Git Commits
If you cloned this repository via Git, you can verify that the commits were genuinely signed by the author:
```bash
git log --show-signature
```

### 3. Verify Release Archives
If you downloaded a compressed source archive (`.tar.gz`) along with its detached signature file (`.asc`), you can verify the archive's integrity before extracting it:
```bash
gpg --verify telegram_code.tar.gz.asc telegram_code.tar.gz
```

## Requirements

The project uses the following Python libraries:
- `pyTelegramBotAPI`
- `mnemonic`
- `pynacl`

## How to Run the Server

Follow these instructions to set up your environment, export your Telegram bot token, and start the HashChat server.

### 1. Set Up a Virtual Environment

It is highly recommended to run the bot inside a Python virtual environment to manage dependencies securely.

```bash
# Create a new virtual environment (if you haven't already)
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate25
```

### 2. Install Dependencies

With the virtual environment activated, install the required packages:

```bash
pip install -r requirements.txt
```

### 3. Export Your Bot Token

You need a Telegram Bot Token to run the server. If you don't have one, talk to [@BotFather](https://t.me/botfather) on Telegram to create a new bot and get your token.

Export the token as an environment variable in your terminal:

```bash
export BOT_TOKEN='your_bot_token_here'
```

### 4. Start the Bot

Once the environment is active and the token is exported, you can run the bot:

```bash
python main.py
```

The bot will print `Bot is starting...` to the console, and it will now be ready to process messages from Telegram!

---
**Note:** For maximum paranoia/security, remember that seed phrases should ideally not be sent over standard Telegram chats since Telegram servers may log standard messages. This bot mitigates risk by instantly deleting the messages where you type your seed phrase/password.
