import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = '8641191453:AAHCr4KDbBjL0Ay5OgSpx8P7QqUSL4wTZCs'

app = Flask(__name__)

application = Application.builder().token(TOKEN).build()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot funcionando en Render!")


application.add_handler(CommandHandler("start", start))


@app.route("/")
def home():
    return "Bot activo"


@app.route("/webhook", methods=["POST"])
async def webhook():
    data = request.get_json(force=True)

    update = Update.de_json(data, application.bot)

    await application.initialize()
    await application.process_update(update)

    return "ok"
