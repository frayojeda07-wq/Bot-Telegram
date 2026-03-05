import telebot

TOKEN = "8243019091:AAEJWzeJcoFmwVRPZdLCACgsSF7fveS0qq4"
bot = telebot.TeleBot(TOKEN)

bot.remove_webhook()

bot.set_webhook(
    url="https://govalue.pythonanywhere.com/webhook"
)

print("Webhook activado")
