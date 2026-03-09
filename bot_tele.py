import os
import sqlite3
from datetime import datetime
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from contextlib import asynccontextmanager

TOKEN = '8641191453:AAHCr4KDbBjL0Ay5OgSpx8P7QqUSL4wTZCs'

# --- 1. BASE DE DATOS (SQLite) ---
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS precios (
            producto TEXT PRIMARY KEY,
            precio REAL
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Base de datos iniciada")

# --- 2. LÓGICA DEL BOT (Estados) ---
# Definimos los estados. ¡Asegúrate de que los nombres coincidan exactamente en todo el código!
INDEX, NEW_VENTAA, NEW_LIST, PRODUCTO, METODO, CANTIDAD, ESPERANDO_PRECIOS = range(7)

# --- PUNTO DE ENTRADA (/start) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Punto de entrada. El usuario escribe /start"""
    # Como es un comando de texto, usamos update.message, NO update.callback_query
    teclado = [
        [InlineKeyboardButton("📦 Nueva Venta", callback_data="new_venta")], # Faltaba la coma al final de esta lista
        [InlineKeyboardButton("📝 Actualizar Lista", callback_data="new_list")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await update.message.reply_text("🤖 ¡Bienvenido a Mi Cajabot!\nUsa mis botones para manejar, es obvio ¿no? 🙄.", reply_markup=reply_markup)
    
    return INDEX # Enviamos al usuario a la sala de espera del índice

# --- MANEJADOR DEL MENÚ PRINCIPAL ---
async def menu_index(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """El usuario tocó un botón del menú principal"""
    query = update.callback_query
    await query.answer()    
    
    seleccion = query.data # ¡Aquí es query.data, no solo query!
    
    if seleccion == "new_list":
        # Si eligió actualizar lista, saltamos directo a la función que pide los precios
        return await pedir_precios(update, context) # Llamamos a la función directamente
    elif seleccion == "new_venta":
        # Si eligió vender, saltamos a la función de iniciar venta
        return await iniciar_venta(update, context)

# --- FLUJO DE PRECIOS ---
async def pedir_precios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # Como venimos de un botón, editamos el mensaje
    mensaje = (
        "📝 **Actualización de Precios**\n\n"
        "Envíame la lista de precios con el formato `Producto: Precio`.\n"
        "Puedes enviar varios en un solo mensaje.\n\n"
        "*Ejemplo:*\n"
        "Botellon: 390\n"
        "Helados Tio Rico: 759\n"
        "Botella 5L: 150"
    )
    await query.edit_message_text(mensaje, parse_mode="Markdown")
    return ESPERANDO_PRECIOS # Ahora el bot espera texto libre

async def guardar_precios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    texto = update.message.text
    lineas = texto.split('\n')
    
    conn = sqlite3.connect('ventas.db')
    cursor = conn.cursor()
    actualizados = []
    
    for linea in lineas:
        if ':' in linea:
            partes = linea.split(':')
            nombre_producto = partes[0].strip()
            try:
                precio = float(partes[1].strip().replace(',', '.'))
                cursor.execute("INSERT OR REPLACE INTO precios (producto, precio) VALUES (?, ?)", (nombre_producto, precio))
                actualizados.append(f"✅ {nombre_producto}: ${precio}")
            except ValueError:
                pass 

    conn.commit()
    conn.close()
    
    if actualizados:
        resumen = "📊 **Precios actualizados con éxito:**\n\n" + "\n".join(actualizados)
    else:
        resumen = "⚠️ No encontré ningún precio válido. Recuerda usar el formato `Producto: Precio`"

    teclado_final = [
        [InlineKeyboardButton("📦 Nueva Venta", callback_data="metodo_Efectivo")],
        [InlineKeyboardButton("📝 Actualizar Lista", callback_data="metodo_PagoMovil")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado_final) 
    await update.message.reply_text(resumen, parse_mode="Markdown")
    await update.message.reply_text("🤖 ¡che Bienvenido a Mi CajaBot \n Usa \
                                     los bototnes para manejar el bot.", reply_markup=reply_markup, parse_mode="Markdown")
    
    return INDEX

# --- FLUJO DE VENTAS ---
async def iniciar_venta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    conn = sqlite3.connect('ventas.db')
    cursor = conn.cursor()
    cursor.execute("SELECT producto, precio FROM precios")
    productos = cursor.fetchall()
    conn.close()

    if not productos:
        await query.edit_message_text("⚠️ Aún no has configurado los precios. Ve al menú e ingresa la lista.")
        return ConversationHandler.END

    teclado = []
    for prod, precio in productos:
        # Usamos un prefijo 'prod_' para identificar que es un botón de producto
        datos_boton = f"prod_{prod[:30]}_{precio}" 
        teclado.append([InlineKeyboardButton(f"{prod} - ${precio}", callback_data=datos_boton)])
    
    reply_markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text("🛒 **NUEVA VENTA**\nSelecciona el producto:", reply_markup=reply_markup, parse_mode="Markdown")
    
    return PRODUCTO

async def seleccionar_producto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # query.data viene como "prod_Botellon_390.0"
    partes = query.data.split('_') 
    # partes[0] es "prod", partes[1] es "Botellon", partes[2] es "390.0"
    context.user_data['producto'] = partes[1]
    context.user_data['precio'] = float(partes[2])
    
    teclado = [
        [InlineKeyboardButton("💵 Efectivo", callback_data="metodo_Efectivo"), InlineKeyboardButton("💳 Punto", callback_data="metodo_Punto")],
        [InlineKeyboardButton("📱 Pago Móvil", callback_data="metodo_PagoMovil")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text(f"Elegiste {context.user_data['producto']}.\n¿Cómo pagó el cliente?", reply_markup=reply_markup)
    
    return METODO

async def seleccionar_metodo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # query.data viene como "metodo_Efectivo"
    context.user_data['metodo'] = query.data.split('_')[1] 
    context.user_data['mensaje_menu_id'] = query.message.message_id
    
    await query.edit_message_text(f"Método: {context.user_data['metodo']}.\n🔢 **Escribe la cantidad** de unidades vendidas (ej. 3):", parse_mode="Markdown")
    
    return CANTIDAD

async def guardar_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    mensaje_usuario_id = update.message.message_id
    mensaje_menu_id = context.user_data.get('mensaje_menu_id')

    try:
        cantidad = int(update.message.text)
    except ValueError:
        await context.bot.delete_message(chat_id=chat_id, message_id=mensaje_usuario_id)
        await context.bot.edit_message_text(
            chat_id=chat_id, 
            message_id=mensaje_menu_id, 
            text="⚠️ **Error:** Envíame solo un número válido.\n🔢 Escribe la cantidad de unidades:", 
            parse_mode="Markdown"
        )
        return CANTIDAD
    
    producto = context.user_data['producto']
    metodo = context.user_data['metodo']
    precio = context.user_data['precio']
    total = cantidad * precio
    
    conn = sqlite3.connect('ventas.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO ventas (producto, cantidad, metodo, total) VALUES (?, ?, ?, ?)", 
                   (producto, cantidad, metodo, total))
    conn.commit()
    conn.close()
    
    resumen = f"✅ *¡Venta Exitosa!*\n📦 {cantidad}x {producto}\n💳 Pago: {metodo}\n💰 Total: ${total:.2f}"
    
    await context.bot.delete_message(chat_id=chat_id, message_id=mensaje_usuario_id)
    await context.bot.edit_message_text(chat_id=chat_id, message_id=mensaje_menu_id, text=resumen, parse_mode="Markdown")
    
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Operación cancelada.")
    return ConversationHandler.END

# --- 3. CONFIGURACIÓN DE FASTAPI ---
# Primero definimos la aplicación de Telegram
application = Application.builder().token(TOKEN).build()

# Luego el Lifespan de FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await application.initialize()
    await application.start() 
    print("🚀 Bot iniciado correctamente")
    yield
    await application.stop()

# Finalmente creamos la app de FastAPI
app = FastAPI(lifespan=lifespan)

# --- 4. CONVERSATION HANDLER ---
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        INDEX: [CallbackQueryHandler(menu_index)],
        # Fíjate en el uso de 'pattern'. Es crucial para no mezclar botones.
        PRODUCTO: [CallbackQueryHandler(seleccionar_producto, pattern="^prod_")],
        METODO: [CallbackQueryHandler(seleccionar_metodo, pattern="^metodo_")],
        CANTIDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_cantidad)],
        ESPERANDO_PRECIOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_precios)]
    },
    fallbacks=[CommandHandler('cancelar', cancelar)]
)

application.add_handler(conv_handler)

# --- 5. RUTAS WEB ---
@app.get("/")
async def root():
    return {"message": "Servidor activo en Render"}

@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.json()
    update = Update.de_json(payload, application.bot)
    await application.process_update(update)
    return {"status": "ok"}
