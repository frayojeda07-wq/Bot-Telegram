import os
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = '8641191453:AAHCr4KDbBjL0Ay5OgSpx8P7QqUSL4wTZCs'

app = FastAPI()

# Inicializa la aplicación del bot
application = Application.builder().token(TOKEN).build()

# Handler para el comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot funcionando con FastAPI en Render!")

# Añadir handler al bot
application.add_handler(CommandHandler("start", start))

@app.get("/")
async def root():
    return {"message": "Bot activo"}

@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.json()
    update = Update.de_json(payload, application.bot)
    await application.initialize()
    await application.process_update(update)
    return {"status": "ok"}
