import telebot
from flask import Flask, request
import os

TOKEN = "8243019091:AAEJWzeJcoFmwVRPZdLCACgsSF7fveS0qq4"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://govalue.pythonanywhere.com{WEBHOOK_PATH}"


@app.route('/')
def index():
    return "Bot funcionando"


@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '', 200


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Bot funcionando correctamente")
