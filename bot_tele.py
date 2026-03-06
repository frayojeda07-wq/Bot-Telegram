
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
    # Tabla de ventas
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
    # NUEVA: Tabla de precios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS precios (
            producto TEXT PRIMARY KEY,
            precio REAL
        )
    ''')
    conn.commit()
    conn.close()

# --- 2. LÓGICA DEL BOT (Menús y Ventas) ---
# Definimos los estados de la conversación
PRODUCTO, METODO, CANTIDAD, ESPERANDO_PRECIOS = range(4)

async def pedir_precios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Se activa con /precios y pide la lista al usuario"""
    mensaje = (
        "📝 **Actualización de Precios**\n\n"
        "Envíame la lista de precios con el formato `Producto: Precio`.\n"
        "Puedes enviar varios en un solo mensaje.\n\n"
        "*Ejemplo:*\n"
        "Botellon: 390\n"
        "Helados Tio Rico: 759\n"
        "Botella 5L: 150"
    )
    await update.message.reply_text(mensaje, parse_mode="Markdown")
    return ESPERANDO_PRECIOS

async def guardar_precios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el texto, lo separa y lo guarda en la base de datos"""
    texto = update.message.text
    lineas = texto.split('\n') # Separamos el mensaje por líneas
    
    conn = sqlite3.connect('ventas.db')
    cursor = conn.cursor()
    
    actualizados = []
    
    for linea in lineas:
        if ':' in linea:
            # Separamos el nombre del producto y el precio
            partes = linea.split(':')
            nombre_producto = partes[0].strip()
            
            try:
                # Convertimos el precio a número (por si usas decimales)
                precio = float(partes[1].strip().replace(',', '.'))
                
                # INSERT OR REPLACE actualiza el precio si ya existe, o lo crea si es nuevo
                cursor.execute("INSERT OR REPLACE INTO precios (producto, precio) VALUES (?, ?)", (nombre_producto, precio))
                actualizados.append(f"✅ {nombre_producto}: ${precio}")
            except ValueError:
                pass # Si alguien puso letras en el precio, lo ignoramos

    conn.commit()
    conn.close()
    
    # Le respondemos al usuario con lo que se guardó
    if actualizados:
        resumen = "📊 **Precios actualizados con éxito:**\n\n" + "\n".join(actualizados)
    else:
        resumen = "⚠️ No encontré ningún precio válido. Recuerda usar el formato `Producto: Precio`"
        
    await update.message.reply_text(resumen, parse_mode="Markdown")
    return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 ¡Bot de la Tienda de Agua activo!\nUsa el comando /vender para registrar una salida.")

async def iniciar_venta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 1: Menú de Productos Dinámico"""
    conn = sqlite3.connect('ventas.db')
    cursor = conn.cursor()
    cursor.execute("SELECT producto, precio FROM precios")
    productos = cursor.fetchall()
    conn.close()

    if not productos:
        await update.message.reply_text("⚠️ Aún no has configurado los precios. Usa el comando /precios primero.")
        return ConversationHandler.END

    # Construimos los botones automáticamente
    teclado = []
    for prod, precio in productos:
        # El callback_data será ej: "Botellon_390.0"
        # Ojo: callback_data tiene un límite de 64 caracteres en Telegram
        datos_boton = f"{prod[:40]}_{precio}" 
        teclado.append([InlineKeyboardButton(f"{prod} - ${precio}", callback_data=datos_boton)])
    
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
    """Paso 3: Pedir la Cantidad y guardar el ID del mensaje"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['metodo'] = query.data
    
    # ¡TRUCO MAGICO! Guardamos el ID de este mensaje de menú en la memoria
    context.user_data['mensaje_menu_id'] = query.message.message_id
    
    await query.edit_message_text(f"Método: {query.data}.\n🔢 **Escribe la cantidad** de unidades vendidas (ej. 3):", parse_mode="Markdown")
    return CANTIDAD

async def guardar_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 4: Guardar, limpiar el chat y mostrar factura"""
    chat_id = update.message.chat_id
    mensaje_usuario_id = update.message.message_id
    mensaje_menu_id = context.user_data.get('mensaje_menu_id')

    try:
        cantidad = int(update.message.text)
    except ValueError:
        # Si escribe letras, borramos lo que escribió y le avisamos editando el menú
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
    
    # --- Guardar en SQLite ---
    conn = sqlite3.connect('ventas.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO ventas (producto, cantidad, metodo, total) VALUES (?, ?, ?, ?)", 
                   (producto, cantidad, metodo, total))
    conn.commit()
    conn.close()
    
    resumen = f"✅ *¡Venta Exitosa!*\n📦 {cantidad}x {producto}\n💳 Pago: {metodo}\n💰 Total: ${total:.2f}"
    
    # 1. Borramos el mensaje donde tú escribiste el número (ej. el "3")
    await context.bot.delete_message(chat_id=chat_id, message_id=mensaje_usuario_id)
    
    # 2. Editamos el menú viejo para que se convierta en la factura final
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=mensaje_menu_id,
        text=resumen,
        parse_mode="Markdown"
    )
    
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
    init_db()
    yield
    await application.stop()

app = FastAPI(lifespan=lifespan)
application = Application.builder().token(TOKEN).build()

# Creamos el manejador de la conversación

conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler('vender', iniciar_venta),
        CommandHandler('precios', pedir_precios) # Agregamos la entrada del nuevo comando
    ],
    states={
        PRODUCTO: [CallbackQueryHandler(seleccionar_producto)],
        METODO: [CallbackQueryHandler(seleccionar_metodo)],
        CANTIDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_cantidad)],
        ESPERANDO_PRECIOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_precios)] # Agregamos el estado de espera
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
