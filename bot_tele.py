import telebot
from fastapi import FastAPI, Request
from telebot import types

TOKEN = '8641191453:AAHCr4KDbBjL0Ay5OgSpx8P7QqUSL4wTZCs'
bot = telebot.TeleBot(TOKEN, threaded=False) # ¡Importante! threaded=False es vital en servidores gratuitos
app = FastAPI()

# 1. COMANDO /START CON MENÚ
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🛒 Nueva Venta", callback_data="vender"))
    markup.add(types.InlineKeyboardButton("📊 Cierre de Caja", callback_data="cierre"))
    bot.send_message(message.chat.id, "💧 *Bienvenido a AguaBot*\n¿Qué deseas hacer hoy?", 
                     parse_mode="Markdown", reply_markup=markup)

# 2. MANEJADOR DE BOTONES (El "cerebro" del menú)
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "vender":
        bot.edit_message_text("🛒 Iniciando proceso de venta...", call.message.chat.id, call.message.message_id)
        # Aquí llamarías a tu función de iniciar venta
    elif call.data == "cierre":
        bot.edit_message_text("📊 Calculando cierre de hoy...", call.message.chat.id, call.message.message_id)

# 3. RUTA WEBHOOK (La puerta de entrada desde Telegram)
@app.post("/webhook")
async def receive_update(request: Request):
    json_str = await request.body()
    update = telebot.types.Update.de_json(json_str.decode("UTF-8"))
    bot.process_new_updates([update])
    return {"status": "ok"}

# 4. CONFIGURAR WEBHOOK AL ARRANCAR
@app.on_event("startup")
async def startup_event():
    # Asegúrate de poner tu URL real de Render aquí abajo
    webhook_url = "https://bot-telegram-ee4q.onrender.com/webhook"
    bot.set_webhook(url=webhook_url)
