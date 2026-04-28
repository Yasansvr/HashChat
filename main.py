import telebot
from bot_instance import bot

# Importing handlers automatically registers them with the bot instance
import handlers

bot.set_my_commands([
    telebot.types.BotCommand("/newkey", "Generate a 12-word seed phrase and get your keys"),
    telebot.types.BotCommand("/delkey", "Delete your active keys"),
    telebot.types.BotCommand("/setpassword", "Lock your 12-word seed phrase with a custom password"),
    telebot.types.BotCommand("/encrypt", "Encrypt and send a message to a friend's public key"),
    telebot.types.BotCommand("/decrypt", "Decrypt a message sent to you"),
    telebot.types.BotCommand("/sign", "Sign a message so others know it's from you"),
    telebot.types.BotCommand("/verify", "Verify a signed message from a friend"),
    telebot.types.BotCommand("/help", "how to use bot"),
    telebot.types.BotCommand("/abouthashchat", "Learn how HashChat keeps you secure"),
])

if __name__ == "__main__":
    print("Bot is starting...")
    bot.infinity_polling()
