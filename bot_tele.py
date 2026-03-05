import os
import telebot
from telebot import types
from flask import Flask, request

TOKEN = "8024972363:AAEsXNGfJCvW6J5UuMp2m_7CgMuYM_XWi5s"

bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

@bot.message_handler(commands=['/start'])
def start(message):
    bot.reply_to(message, "🤖 Bot funcionando en Render!")

@app.route("/", methods=["GET"])
def home():
    return "Bot activo"

@app.route("/webhook", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@bot.message_handler(func=lambda m: True)
def debug(message):
    print("Mensaje:", message.text)
    bot.reply_to(message, "Recibí: " + message.text)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
