import os
import sqlite3
from datetime import datetime
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from contextlib import asynccontextmanager

# --------- 1. VARIABLES GLOBALES ----------

TOKEN = '8641191453:AAHCr4KDbBjL0Ay5OgSpx8P7QqUSL4wTZCs'
password_admin = "132435"


# ---------- 2. BASE DE DATOS -----------

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

# ---------- 3. LÓGICA DEL BOT -----------

INDEX, PASSWORD, NEW_VENTAA, NEW_LIST, PRODUCTO, METODO, CANTIDAD, ESPERANDO_PRECIOS = range(8)


# ---------- 4. ENTRADA (/start) -----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    teclado = [
        [InlineKeyboardButton("📦 Nueva Venta", callback_data="new_venta")], # Faltaba la coma al final de esta lista
        [InlineKeyboardButton("📝 Actualizar Lista", callback_data="new_list")],
        [InlineKeyboardButton("🧮 cerrar caja", callback_data="closed")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await update.message.reply_text("🤖 ¡Bienvenido a Mi Cajabot!\nUsa mis botones para manejar, es obvio ¿no? 🙄.", reply_markup=reply_markup)
    
    return INDEX 


# ----------- 5. ENRUTADOR ------------

async def menu_index(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()    
    
    seleccion = query.data 
    
    if seleccion == "new_list":
        return await pedir_precios(update, context) 
    elif seleccion == "new_venta":
        return await iniciar_venta(update, context)
    elif seleccion == "closed":
        return await pedir_contraseña(update, context) 


# --------- 6. SEGURIDAD DEL CIERRE ----------- 

async def pedir_contraseña(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data['mensaje_menu_id'] = query.message.message_id
    
    await query.edit_message_text("**Escribe la contraseña para continuar:**", parse_mode="Markdown")
    
    return PASSWORD


# --------- 7. VERIFICACION PASSWORD ----------
    
async def verify_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text 
    if texto == password_admin:
        return await iniciar_cierre(update, context) 
    else:
        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
   
        await update.message.reply_text("🤖 Error de contraseña. Vuelve a escribirla:")
        
        return PASSWORD   
          

# -------- 8. CALCULATOR CLOSED ---------
"""
async def iniciar_cierre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    conn = sqlite3.connect('ventas.db')
    cursor = conn.cursor()
    cursor.execute("SELECT total FROM ventas")
    cierre_total = cursor.fetchall()
    conn.close()        
    
    total_venta =[]
 
for total_ventas in cierre_total: 
    vetasss = total_ventas
    total_venta.append(vetasss)"""
    
    
# ----------- 9. FLUJO DE PRECIOS ------------

async def pedir_precios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
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
    return ESPERANDO_PRECIOS 


# ----------- 10. GUARDADO DE PRECIOS ------------

async def guardar_precios(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        [InlineKeyboardButton("📦 Nueva Venta", callback_data="new_venta")],
        [InlineKeyboardButton("📝 Actualizar Lista", callback_data="new_list")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado_final) 

    await update.message.reply_text(resumen, parse_mode="Markdown")
    await update.message.reply_text(
        "🤖 ¡Che! Bienvenido a Mi CajaBot.\nUsa los botones para manejar el bot.", 
        reply_markup=reply_markup, 
        parse_mode="Markdown"
    )
    
    return INDEX


# ----------- 11. FLUJO DE VENTAS ----------

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
        datos_boton = f"{prod[:30]}_{precio}" 
        teclado.append([InlineKeyboardButton(f"{prod} - ${precio}", callback_data=datos_boton)])
    
    reply_markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text("🛒 **NUEVA VENTA**\nSelecciona el producto:", reply_markup=reply_markup, parse_mode="Markdown")
    
    return PRODUCTO


# ----------- 12. FLUJO DE PRECIOS ------------

async def seleccionar_producto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    datos_producto = query.data.split('_') 
    context.user_data['producto'] = datos_producto[0]
    context.user_data['precio'] = float(datos_producto[1])
    
    teclado = [
        [InlineKeyboardButton("💵 Efectivo", callback_data="Efectivo"), InlineKeyboardButton("💳 Punto", callback_data="Punto")],
        [InlineKeyboardButton("📱 Pago Móvil", callback_data="PagoMovil")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text(f"Elegiste {context.user_data['producto']}.\n¿Cómo pagó el cliente?", reply_markup=reply_markup)
    return METODO


# ----------- 13. FLUJO DE PRECIOS ------------

async def seleccionar_metodo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['metodo'] = query.data

    context.user_data['mensaje_menu_id'] = query.message.message_id
    
    await query.edit_message_text(f"Método: {query.data}.\n🔢 **Escribe la cantidad** de unidades vendidas (ej. 3):", parse_mode="Markdown")
    return CANTIDAD


# ----------- 14. FLUJO DE PRECIOS ------------

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
    
    teclado_final = [
        [InlineKeyboardButton("📦 Nueva Venta", callback_data="new_venta")],
        [InlineKeyboardButton("📝 Actualizar Lista", callback_data="new_list")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado_final) 
    
    await context.bot.delete_message(chat_id=chat_id, message_id=mensaje_usuario_id)
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=mensaje_menu_id,
        text=resumen,
        parse_mode="Markdown"
    )
    await update.message.reply_text(
        "🤖 ¡Che! Bienvenido a Mi CajaBot.\nUsa los botones para manejar el bot.", 
        reply_markup=reply_markup, 
        parse_mode="Markdown"
    )
    
    return INDEX


# ----------- 15. FLUJO DE PRECIOS ------------

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Venta cancelada.")
    return ConversationHandler.END


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
        CommandHandler('start', start), # ¡El /start tiene que estar aquí adentro!
        CommandHandler('vender', iniciar_venta),
        CommandHandler('precios', pedir_precios)
    ],
    states={
        INDEX: [CallbackQueryHandler(menu_index)],
        PRODUCTO: [CallbackQueryHandler(seleccionar_producto)], # Tip: Te recomiendo volver a poner los pattern="^..." que te enseñé
        METODO: [CallbackQueryHandler(seleccionar_metodo)],
        CANTIDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_cantidad)],
        ESPERANDO_PRECIOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_precios)],
        PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_password)] # <- AQUÍ AGREGAMOS LA ESCUCHA DE LA CONTRASEÑA
    },
    fallbacks=[CommandHandler('cancelar', cancelar)]
)

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
