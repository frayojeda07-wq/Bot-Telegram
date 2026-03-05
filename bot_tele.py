
import os
import sqlite3
from datetime import datetime
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from contextlib import asynccontextmanager

TOKEN = '8641191453:AAHCr4KDbBjL0Ay5OgSpx8P7QqUSL4wTZCs'

# --- 1. BASE DE DATOS (SQLite temporal para pruebas) ---
def init_db():
    conn = sqlite3.connect('ventas.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto TEXT,
            cantidad INTEGER,
            metodo TEXT,
            total REAL,
            fecha DATE DEFAULT CURRENT_DATE
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- 2. LÓGICA DEL BOT (Menús y Ventas) ---
# Definimos los estados de la conversación
PRODUCTO, METODO, CANTIDAD = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 ¡Bot de la Tienda de Agua activo!\nUsa el comando /vender para registrar una salida.")

async def iniciar_venta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 1: Menú de Productos"""
    teclado = [
        [InlineKeyboardButton("💧 Botellón 20L", callback_data="Botellon_1.5")], # El 1.5 es el precio simulado
        [InlineKeyboardButton("🚰 Botella 5L", callback_data="Botella_0.5")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await update.message.reply_text("🛒 **NUEVA VENTA**\nSelecciona el producto:", reply_markup=reply_markup, parse_mode="Markdown")
    return PRODUCTO

async def seleccionar_producto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 2: Menú de Método de Pago"""
    query = update.callback_query
    await query.answer()
    
    # Guardamos qué producto y precio eligió
    datos_producto = query.data.split('_') # Divide "Botellon_1.5" en ["Botellon", "1.5"]
    context.user_data['producto'] = datos_producto[0]
    context.user_data['precio'] = float(datos_producto[1])
    
    teclado = [
        [InlineKeyboardButton("💵 Efectivo", callback_data="Efectivo"), InlineKeyboardButton("💳 Punto", callback_data="Punto")],
        [InlineKeyboardButton("📱 Pago Móvil", callback_data="PagoMovil")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text(f"Elegiste {context.user_data['producto']}.\n¿Cómo pagó el cliente?", reply_markup=reply_markup)
    return METODO

async def seleccionar_metodo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 3: Pedir la Cantidad"""
    query = update.callback_query
    await query.answer()
    
    # Guardamos el método de pago
    context.user_data['metodo'] = query.data
    
    await query.edit_message_text(f"Método: {query.data}.\n🔢 **Escribe la cantidad** de unidades vendidas (ej. 3):", parse_mode="Markdown")
    return CANTIDAD

async def guardar_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 4: Guardar en DB y finalizar"""
    try:
        cantidad = int(update.message.text)
    except ValueError:
        await update.message.reply_text("⚠️ Por favor, envíame solo un número válido. Intenta de nuevo:")
        return CANTIDAD # Lo dejamos en el mismo estado hasta que mande un número
    
    producto = context.user_data['producto']
    metodo = context.user_data['metodo']
    precio = context.user_data['precio']
    total = cantidad * precio
    
    # Guardar en SQLite
    conn = sqlite3.connect('ventas.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO ventas (producto, cantidad, metodo, total) VALUES (?, ?, ?, ?)", 
                   (producto, cantidad, metodo, total))
    conn.commit()
    conn.close()
    
    resumen = f"✅ *¡Venta Exitosa!*\n📦 {cantidad}x {producto}\n💳 {metodo}\n💰 Total: ${total:.2f}"
    await update.message.reply_text(resumen, parse_mode="Markdown")
    
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Permite cancelar la venta a la mitad"""
    await update.message.reply_text("🚫 Venta cancelada.")
    return ConversationHandler.END

# --- 3. CONFIGURACIÓN DE FASTAPI Y EL BOT ---

# Configuramos el ciclo de vida para que el bot inicie correctamente con FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    await application.initialize()
    await application.start()
    yield
    await application.stop()

app = FastAPI(lifespan=lifespan)
application = Application.builder().token(TOKEN).build()

# Creamos el manejador de la conversación
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('vender', iniciar_venta)],
    states={
        PRODUCTO: [CallbackQueryHandler(seleccionar_producto)],
        METODO: [CallbackQueryHandler(seleccionar_metodo)],
        CANTIDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_cantidad)]
    },
    fallbacks=[CommandHandler('cancelar', cancelar)]
)

application.add_handler(CommandHandler("start", start))
application.add_handler(conv_handler)

# --- 4. RUTAS WEB ---
@app.get("/")
async def root():
    return {"message": "Servidor activo en Render"}

@app.post("/webhook")
async def webhook(request: Request):
    # Recibe el mensaje de Telegram y lo procesa
    payload = await request.json()
    update = Update.de_json(payload, application.bot)
    await application.process_update(update)
    return {"status": "ok"}
