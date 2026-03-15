import os
import sqlite3
from groq import Groq
from openai import OpenAI
from datetime import datetime
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# --------- 1. VARIABLES GLOBALES ----------

cliente_groq = OpenAI(
    api_key="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", 
    base_url="https://api.groq.com/openai/v1",
)
TOKEN = "8641191453:AAHCr4KDbBjL0Ay5OgSpx8P7QqUSL4wTZCs"
password_admin = "132435”

# ---------- 2. BASE DE DATOS -----------

def init_db():
    conn = sqlite3.connect('ventas.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_telegran_id TEXT,
            producto TEXT,
            cantidad INTEGER,
            metodo TEXT,
            total REAL,
            fecha DATE DEFAULT CURRENT_DATE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tienda (
            user_telegran_id TEXT PRIMARY KEY,
            password_user REAL,
            method_payments TEXT,
            data_bcv_day REAL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS precios ( 
            producto TEXT PRIMARY KEY,
            user_telegran_id TEXT,
            precio REAL
        )
    ''')
    conn.commit()
    conn.close()

# ---------- 3. PASOS DEL BOT -----------

INDEX, PASSWORD, NEW_VENTAA, NEW_LIST, PRODUCTO, METODO, CANTIDAD, ESPERANDO_PRECIOS = range(8)


# ---------- 4. ENTRADA (/start) -----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    teclado = [
        [InlineKeyboardButton("📦 Nueva Venta", callback_data="new_venta")], 
        [InlineKeyboardButton("📝 Actualizar Lista", callback_data="new_list")],
        [InlineKeyboardButton("🧮 Cerrar caja", callback_data="closed")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
   
    texto_bienvenida = (
        "**Bienvenido a Mi CajaBot.**\n\n"
        "Somos un pequeño Gestor de tienda\n"
        "desarrollado por AgoraSystem líder en \n"
        "sistemas de tiendas, bases de datos y\n"
        "bot de autogestión.\n\n"
        "¿Qué hace este bot en específico?:\n\n"
        "1. Gestiona tu inventario:\n"
        "   Podés subir, actualizar, eliminar\n"
        "   y administrar tus productos con\n"
        "   simples botones y menús sencillos.\n\n"
        "2. Gestiona ventas:\n"
        "   Podés gestionar todas las ventas,\n"
        "   fiados, cálculos y demás con una\n"
        "   interfaz super sencilla.\n\n"
        "3. Gestión de consumos internos:\n"
        "   Podés llevar control de los gastos\n"
        "   internos, pérdidas de productos,\n"
        "   pagos y salarios.\n\n"
        "4. Inteligencia artificial:\n"
        "   Con un comando podés\n"
        "   iniciar una conversación con\n"
        "   el modelo Llama de Meta para\n"
        "   preguntar cómo van las ventas,\n"
        "   precio de un producto específico,\n"
        "   cuánto llevás en efectivo hasta el\n"
        "   momento, registrar consumos, etc.\n\n"
        "5. Manejo de Cierre de caja:\n"
        "   Al final del día podés llevar\n"
        "   registro de lo que se hizo en el\n"
        "   día, cuánto se recaudó en cada\n"
        "   método de pago, productos más\n"
        "   vendidos, subtotales y mucho más\n"
        "   en un sólo mensaje bien\n"
        "   estructurado y fácil de entender.\n\n"
        "Mi CajaBot es 100% gratuito y\n"
        "diseñado para el pequeño\n"
        "emprendedor y llevar control de su\n"
        "negocio sin necesidad de sistemas\n"
        "complejos ni computadoras.\n"
        "Todo desde Telegram y tu móvil.\n\n"
        "Recordá que si querés un sistema más\n"
        "completo, profesional y de gran magnitud\n"
        "de ventas podés buscar en nuestro sitio web\n"
        "un sistema que se adapte a tu negocio.")

    await update.message.reply_text(
        texto_bienvenida, 
        parse_mode='Markdown'
    )
    
    await update.message.reply_text(
        "**Menú principal**\nIniciá una venta", 
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
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
    else:
        # Si el callback no coincide, volver a mostrar menú
        return INDEX


# --------- 6. SEGURIDAD DEL CIERRE ----------- 

async def pedir_contraseña(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data['mensaje_menu_id'] = query.message.message_id
    
    await query.edit_message_text("**Escribí la contraseña para continuar:** \n\n\nPara ir al menú principal\nEnvía /cancelar", parse_mode="Markdown")
    
    return PASSWORD


# --------- 7. VERIFICACION PASSWORD ----------
    
async def verify_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text 
    if texto == password_admin:
        return await iniciar_cierre(update, context) 
    else:
        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
   
        await update.message.reply_text("🤖 Error de contraseña. Volvé a escribirla:")
        
        return PASSWORD   
          

# -------- 8. CALCULATOR CLOSED ---------
    
async def iniciar_cierre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('ventas.db')
    cursor = conn.cursor()

    # --- Cálculos por Método ---
    cursor.execute("SELECT SUM(total) FROM ventas WHERE metodo = 'Efectivo' AND fecha = CURRENT_DATE")
    efectivo = cursor.fetchone()[0] or 0.0

    cursor.execute("SELECT SUM(total) FROM ventas WHERE metodo = 'Punto' AND fecha = CURRENT_DATE")
    punto = cursor.fetchone()[0] or 0.0 

    cursor.execute("SELECT SUM(total) FROM ventas WHERE metodo = 'PagoMovil' AND fecha = CURRENT_DATE")
    pago_movil = cursor.fetchone()[0] or 0.0

    # --- Cálculos por Producto ---
    cursor.execute("SELECT SUM(total) FROM ventas WHERE producto LIKE '%Botellon%' AND fecha = CURRENT_DATE")
    botellones = cursor.fetchone()[0] or 0.0

    cursor.execute("SELECT SUM(total) FROM ventas WHERE producto LIKE '%Helado%' AND fecha = CURRENT_DATE")
    helados = cursor.fetchone()[0] or 0.0 

    # --- Gran Total ---
    total_general = efectivo + punto + pago_movil
    
    conn.close()

    # --- Mensaje Final ---
    mensaje = (
        "📊 **CIERRE DE CAJA COMPLETO**\n\n"
        f"💧 Total Botellones: ${botellones}\n"
        f"🍦 Total Helados: ${helados}\n"
        "--------------------------\n"
        f"💵 Efectivo: ${efectivo}\n"
        f"💳 Punto: ${punto}\n"
        f"📱 Pago Móvil: ${pago_movil}\n\n"
        f"💰 **TOTAL AL CIERRE: ${total_general}**"
    )
    teclado = [
        [InlineKeyboardButton("📁 Guardar db", callback_data="save_db"), InlineKeyboardButton("♻️ Reiniciar", callback_data="reset_db")],
        [InlineKeyboardButton("🧐 Verificar Stocks", callback_data="view_stock")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await update.message.reply_text(mensaje, parse_mode="Markdown")
    await update.message.reply_text("¡Éxito! Tu cierre ha sido perfecto 📝.\n\n¿Ahora qué sigue?", parse_mode="Markdown", reply_markup=reply_markup)
    return INDEX


# ----------- 9. FLUJO DE PRECIOS ------------

async def pedir_precios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    mensaje = (
        "📝 **Actualización de Precios**\n\n"
        "Envíame la lista de precios con el formato `Producto: Precio`.\n"
        "Podés enviar varios en un solo mensaje.\n\n"
        "*Ejemplo:*\n"
        "Botellon: 390\n"
        "Helados Tio Rico: 759\n"
        "Botella 5L: 150 \n\n\nPara ir al menú principal\nEnvía /cancelar"
    )
    await query.edit_message_text(mensaje, parse_mode="Markdown")
    return ESPERANDO_PRECIOS 


# ----------- 10. GUARDADO DE PRECIOS ------------

async def guardar_precios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    lineas = texto.split('\n')
    user_tienda = update.effective_user.id
    conn = sqlite3.connect('ventas.db')
    cursor = conn.cursor()
    actualizados = []
    
    for linea in lineas:
        if ':' in linea:
            partes = linea.split(':')
            nombre_producto = partes[0].strip()
            try:
                precio = float(partes[1].strip().replace(',', '.'))
                cursor.execute("INSERT OR REPLACE INTO precios (producto, precio, user_telegran_id) VALUES (?, ?, ?)", (nombre_producto, precio, user_tienda))
                actualizados.append(f"✅ {nombre_producto}: ${precio}")
            except ValueError:
                pass 

    conn.commit()
    conn.close()
    
    if actualizados:
        resumen = "📊 **Precios actualizados con éxito:**\n\n" + "\n".join(actualizados)
    else:
        resumen = "⚠️ No encontré ningún precio válido. Recordá usar el formato `Producto: Precio`"

    teclado_final = [
        [InlineKeyboardButton("📦 Nueva Venta", callback_data="new_venta")],
        [InlineKeyboardButton("📝 Actualizar Lista", callback_data="new_list")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado_final) 

    await update.message.reply_text(resumen, parse_mode="Markdown")
    await update.message.reply_text(
        "¡Éxito! Tu inventario se ha guardado 📝.\n\n¿Ahora qué sigue?", 
        reply_markup=reply_markup, 
        parse_mode="Markdown"
    )
    
    return INDEX


# ----------- 11. FLUJO DE VENTAS ----------

async def iniciar_venta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    conn = sqlite3.connect('ventas.db')
    cursor = conn.cursor()
    user_tienda = update.effective_user.id 
    cursor.execute("SELECT producto, precio FROM precios WHERE user_telegran_id = ?", (user_tienda,))
    productos = cursor.fetchall()
    conn.close()

    if not productos:
        await query.edit_message_text("⚠️ Aún no has configurado los precios. Andá al menú e ingresá la lista.")
        return INDEX

    teclado = []
    for prod, precio in productos:
        datos_boton = f"{prod[:30]}_{precio}" 
        teclado.append([InlineKeyboardButton(f"{prod} - ${precio}", callback_data=datos_boton)])
    
    reply_markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text("🛒 **NUEVA VENTA**\nSeleccioná el producto: \n\n\nPara ir al menú principal\nEnvía /cancelar ", reply_markup=reply_markup, parse_mode="Markdown")
    
    return PRODUCTO


# ----------- 12. SELECCIONAR PRODUCTO ------------

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
    await query.edit_message_text(f"Elegiste {context.user_data['producto']}.\n¿Cómo pagó el cliente?\n\n\nPara ir al menú principal\nEnvía /cancelar", reply_markup=reply_markup)
    return METODO


# ----------- 13. SELECCIONAR MÉTODO ------------

async def seleccionar_metodo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['metodo'] = query.data

    context.user_data['mensaje_menu_id'] = query.message.message_id
    
    await query.edit_message_text(f"Método: {query.data}.\n🔢 **Escribí la cantidad** de unidades vendidas (ej. 3):\n\n\nPara ir al menú principal\nEnvía /cancelar", parse_mode="Markdown")
    return CANTIDAD


# ----------- 14. GUARDAR CANTIDAD ------------

async def guardar_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_tienda = update.effective_user.id
    mensaje_usuario_id = update.message.message_id
    mensaje_menu_id = context.user_data.get('mensaje_menu_id')

    try:
        cantidad = int(update.message.text)
    except ValueError:
        await context.bot.delete_message(chat_id=chat_id, message_id=mensaje_usuario_id)
        await context.bot.edit_message_text(
            chat_id=chat_id, 
            message_id=mensaje_menu_id, 
            text="⚠️ **Error:** Envíame solo un número válido.\n🔢 Escribí la cantidad de unidades:", 
            parse_mode="Markdown"
        )
        return CANTIDAD
    
    producto = context.user_data['producto']
    metodo = context.user_data['metodo']
    precio = context.user_data['precio']
    total = cantidad * precio
    
    conn = sqlite3.connect('ventas.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO ventas (producto, cantidad, user_telegran_id, metodo, total) VALUES (?, ?, ?, ?, ?)", 
                   (producto, cantidad, user_tienda, metodo, total))
    conn.commit()
    conn.close()
    
    resumen = f"✅ *¡Venta Exitosa!*\n📦 {cantidad}x {producto}\n💳 Pago: {metodo}\n💰 Total: ${total:.2f}"
    
    teclado_final = [
        [InlineKeyboardButton("📊 Ver Stocks", callback_data="view_stock")],
        [InlineKeyboardButton("🗃️ Ver resumen", callback_data="view_sells")],
        [InlineKeyboardButton("📦 Nueva Venta", callback_data="new_venta")]
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
        "¡Éxito! Tu venta se ha guardado 📝.\n\n¿Ahora qué sigue?", 
        reply_markup=reply_markup, 
        parse_mode="Markdown"
    )
    
    return INDEX


# ----------- 15. CANCELAR ------------

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teclado = [
        [InlineKeyboardButton("📦 Nueva Venta", callback_data="new_venta")], 
        [InlineKeyboardButton("📝 Actualizar Lista", callback_data="new_list")],
        [InlineKeyboardButton("🧮 Cerrar caja", callback_data="closed")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await update.message.reply_text("🚫 Operación cancelada.\n\n¿A dónde vamos?", reply_markup=reply_markup)
    
    return INDEX


# ----------- 16. RESPUESTA IA  ------------

async def responder_con_ia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await update.message.reply_chat_action(action="typing")

    try:
        # 1. Consultamos la base de datos
        conn = sqlite3.connect('ventas.db')
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(total) FROM ventas WHERE fecha = CURRENT_DATE")
        total_hoy = cursor.fetchone()[0] or 0.0
        
        cursor.execute("SELECT producto, SUM(cantidad) as total_vendido FROM ventas GROUP BY producto ORDER BY total_vendido DESC LIMIT 3")
        mas_vendidos = cursor.fetchall()
        conn.close()

        resumen_db = f"Ventas totales de hoy: ${total_hoy}. Productos top: {mas_vendidos}."

        response = cliente_groq.chat.completions.create(
            messages=[
                {
                    "role": "system", 
                    "content": f"Eres el asistente financiero de Mi CajaBot. Tenés estos datos de la base de datos: {resumen_db}. Respondé siempre basándote en estos números, sé amable en tus respuestas y profesional."
                },
                {"role": "user", "content": user_text}
            ],
            model="llama-3.1-8b-instant",
        )
        
        await update.message.reply_text(f"👤 Respuesta IA:\n\n{response.choices[0].message.content}\n\nTerminar conversación\n/menu")
        
    except Exception as e:
        print(f"ERROR: {e}")
        await update.message.reply_text("🤖 Ups, tuve un pequeño problema procesando tus datos.")

    return INDEX



# ---------- 17. INICIO DE FastAPI ------------ 

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await application.initialize()
    await application.start() 
    yield
    await application.stop()
    await application.shutdown()

app = FastAPI(lifespan=lifespan)
application = Application.builder().token(TOKEN).build()


# ------------ 18. HANDLER CONVERSATION ----------

conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler('start', start), 
        CommandHandler('vender', iniciar_venta),
        CommandHandler('precios', pedir_precios)
    ],
    states={
        INDEX: [
            CallbackQueryHandler(menu_index),
            MessageHandler(filters.TEXT & ~filters.COMMAND, responder_con_ia)
        ],
        PRODUCTO: [CallbackQueryHandler(seleccionar_producto)], 
        METODO: [CallbackQueryHandler(seleccionar_metodo)],
        CANTIDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_cantidad)],
        ESPERANDO_PRECIOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_precios)],
        PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_password)] 
    },
    fallbacks=[
        CommandHandler('start', start), 
        CommandHandler('cancelar', cancelar),
        CommandHandler('menu', cancelar)
    ],
    allow_reentry=True 
)

application.add_handler(conv_handler)


# ----------- 19. RUTAS WEB -------------

@app.get("/")
async def root():
    return {"message": "Servidor activo en Render"}

@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.json()
    update = Update.de_json(payload, application.bot)
    await application.process_update(update)
    return {"status": "ok"}
