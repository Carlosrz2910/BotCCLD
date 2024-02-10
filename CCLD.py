from datetime import datetime, timedelta
from flask import request, jsonify, Flask
from telebot.types import InputFile
from pyngrok import ngrok, conf
from urllib.parse import urlparse
from waitress import serve
from telebot import types
from io import BytesIO
import mercadopago
import psycopg2
import requests
import random
import telebot
import qrcode
import string
import time
import uuid
import pytz
import json
import os
from ssh_module import *

def leer_config(archivo_config):
    with open(archivo_config, 'r') as f:
        config = json.load(f)
    return config
    
config = leer_config("./config.json")

TOKEN = config.get("TOKEN", "")
NGROK_TOKEN = config.get("NGROK_TOKEN", "")
TELEGRAM_CHANNEL = config.get("TELEGRAM_CHANNEL", "")
SERVER_IP = config.get("SERVER_IP", "")
SERVER_PORT = config.get("SERVER_PORT", "")
ROOT_USER = config.get("ROOT_USER", "")
ROOT_PASS = config.get("ROOT_PASS", "")
MERCADO_PAGO_TOKEN = config.get("MERCADO_PAGO_TOKEN", "")
DATABASE_URL = config.get("DATABASE_URL", "")
TEMPO_TES = config.get("TEMPO_TES", "")
DIAS_ESPERA = config.get("DIAS_ESPERA", "")
VPN_NOMBRE = config.get("VPN_NOMBRE", "")
NM_USUARIO = config.get("NM_USUARIO", "")
MONTO_1 = config.get("MONTO_1","")
MONTO_2 = config.get("MONTO_2","")
MONTO_3 = config.get("MONTO_3","")


bot = telebot.TeleBot(TOKEN)
web_server = Flask(__name__)
sdk = mercadopago.SDK(MERCADO_PAGO_TOKEN)
user_names = {} # Guarda temporalmente el nombre del usurio de telegram para insertarlos en la databade
failed_attempts = {} # Diccionario para rastrear los intentos fallidos
successful_changes = {} # Diccionario para rastrear los cambios exitosos de contraseña
payment_info_by_id = {} # Para que en la función process_ssh_payment no de error al recibir la información del server

@web_server.route('/', methods=['POST'])
def webhook(): 
    if request.headers.get("Content-Type") == "application/json":
        json_string = request.stream.read().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        
        if update.message:
            bot.process_new_messages([update.message])
        elif update.callback_query:
            bot.process_new_callback_query([update.callback_query])
        
        return "OK", 200
    else:
        return "Invalid request", 400
        
def get_expiration_minutes():
    with open('./config.json', 'r') as file:
        config = json.loads(file.read())
    return int(config['expiration_payment_in_minutes'])

def create_payment(value, description, chat_id):
    try:
        expiration_minutes = get_expiration_minutes()
        expire = datetime.now() + timedelta(minutes=expiration_minutes)
        expire = expire.strftime("%Y-%m-%dT%H:%M:%S.000-03:00")

        payer_email = f"{chat_id}@ccldpay.com"

        payment_data = {
            "transaction_amount": int(value),
            "payment_method_id": 'pix',
            "installments": 1,
            "description": description,
            "date_of_expiration": f"{expire}",
            "payer": {
                "email": payer_email
            }
        }
        result = sdk.payment().create(payment_data)
        return result
    except Exception as e:
        print(f"Error creating payment: {e}")
        return None
        
def expiration():
    expiration_minutes = get_expiration_minutes()
    time_change = datetime.timedelta(minutes=expiration_minutes)
    new_time = datetime.datetime.now() + time_change

    tz = pytz.timezone("America/Bahia")
    aware_dt = tz.localize(new_time)

    a = aware_dt.isoformat()

    return a[:23]+a[26:]
        
@bot.callback_query_handler(func=lambda call: call.data == 'descargar_app')
def send_apk(call): 
    chat_id = call.message.chat.id
    with open(f"{VPN_NOMBRE}.apk", "rb") as apk_file:
        caption_text = f"<b>Aqui você tem o APP {VPN_NOMBRE}⚡️ Baixe e instale! 📦</b>"
        bot.send_document(chat_id, apk_file, caption=caption_text, parse_mode='HTML')
    bot.answer_callback_query(call.id)

    qr_code_data = payment['response']['point_of_interaction']['transaction_data']['qr_code']
    send_qr_code(message.chat.id, qr_code_data)
    bot.send_message(message.chat.id, f"Chave Pix (base64):💠\n\n<code>{qr_code_data}</code>", parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == 'atualizar_acesso')
def submenu_aztualizar(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_cambiar_accseo = types.InlineKeyboardButton('ATUALIZAR ACESSO 🔏', callback_data='renovar_acceso')
    btn_cambiar_contraseña = types.InlineKeyboardButton('TROCAR SENHA 🔐', callback_data='cambiar_contraseña')
    btn_voltar = types.InlineKeyboardButton("Voltar ao inicio 🔙", callback_data='voltar_inicio')
    markup.add(btn_cambiar_accseo, btn_cambiar_contraseña, btn_voltar)
    
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                          text=f"<b>Olá</b>, ao entrar nesta seção você pode optar por:\n\nAtualizar seu acesso renovando o pagamento 🤌🏻\nou\nAlterando sua senha, ta bom? 👌🏻\n\n"
                          f"<b>DICA E OBSERVAÇÃO: 📍</b>\n\n1. Você só tem 3 tentativas para alterar sua senha❗️\n\n2. Depois de alterar sua senha, você não poderá fazê-lo até 15 dias❗️\n\n"
                          f"<b>‼️MUITO IMPORTANTE‼️</b> Renovação é apenas para contas SSH expiradas, Se você pagar uma renovação antes do vencimento, os dias que já tinha "
                          f"não serão somados e você perderá seu dinheiro sem direito a reembolso. Se quiser fazer esse processo, "
                          f"fale com o <a href='https://t.me/{NM_USUARIO}'>Proprietário</a> 📞", reply_markup=markup, parse_mode='HTML', disable_web_page_preview=True)

@bot.callback_query_handler(func=lambda call: call.data == 'cambiar_contraseña')
def cambiar_contraseña(call): # Funcion de cambiar la contraseña
    chat_id = call.message.chat.id
    
    msg = bot.send_message(chat_id, "Por favor, digite o nome de usuário para alterar a senha 🔐")
    bot.register_next_step_handler(msg, ask_for_new_password)

def ask_for_new_password(message):
    chat_id = message.chat.id
    username = message.text
    
    msg = bot.send_message(chat_id, "Por favor, digite a nova senha que deseja usar 🔓")
    bot.register_next_step_handler(msg, process_new_password, username)
    
def process_new_password(message, username):
    chat_id = message.chat.id
    new_password = message.text

    last_successful_change = successful_changes.get(chat_id, None)
    if last_successful_change and datetime.now() - last_successful_change < timedelta(days=15):
        bot.send_message(chat_id, "Você alterou sua senha recentemente. Você não pode alterá-lo novamente até 15 dias ⭕️")
        return
        
    attempts, last_attempt_time = failed_attempts.get(chat_id, (0, None))
    if attempts >= 3 and last_attempt_time and datetime.now() - last_attempt_time < timedelta(hours=3):
        bot.send_message(chat_id, "Você excedeu o número máximo de tentativas. Tente novamente em 3 horas ❌")
        return
    
    telegram_username = user_names.get(chat_id, "Desconocido")
    
    client = get_ssh_client(SERVER_IP, SERVER_PORT, ROOT_USER, ROOT_PASS)
    
    response = change_ssh_user_password(client, username, new_password)
    
    if response == "O usuário não existe, a senha não pode ser alterada ‼️":
        failed_attempts[chat_id] = (attempts + 1, datetime.now())
        bot.send_message(chat_id, response + " Você tentou " + str(attempts + 1) + " vezes. Após 3 tentativas fracassadas, você terá que esperar 3 horas ⛔️")
        return
    
    if chat_id in failed_attempts: # Restablecer los intentos fallidos si el cambio fue exitoso
        del failed_attempts[chat_id]

    bot.send_message(chat_id, response)     # Enviar la respuesta al usuario   

    if response == "Senha alterada com sucesso ✅":     # Registrar el cambio exitoso si la respuesta indica éxito
        successful_changes[chat_id] = datetime.now()
        update_password_and_tracking(username, new_password)
        bot.send_message(TELEGRAM_CHANNEL, f"El usuario {telegram_username} con el usuario SSH: {username}\n\nCambió su contraseña a: {new_password} ⭕️")

@bot.message_handler(commands=['start'])
def cmd_start(message):
    chat_id = message.chat.id
    user_name = f"{message.from_user.first_name}" if message.from_user.first_name else "Usuario"
    user_names[chat_id] = user_name  # Guardas el nombre en el diccionario.
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_soporte = types.InlineKeyboardButton("⚙️ SOPORTE", url=f'https://t.me/{NM_USUARIO}')
    btn_comprar = types.InlineKeyboardButton("💎 COMPRAR ACCESSO 💎", callback_data='comprar_acesso')
    btn_descargar_app = types.InlineKeyboardButton(f"BAIXAR {VPN_NOMBRE} 📦", callback_data='descargar_app')
    btn_atualizar_acesso = types.InlineKeyboardButton("ATUALIZAR ACESSOS 🔏", callback_data='atualizar_acesso')
    btn_teste = types.InlineKeyboardButton("GERAR TESTE 🎯", callback_data='gerar_teste')
    markup.add(btn_soporte, btn_comprar, btn_descargar_app, btn_atualizar_acesso, btn_teste)
    
    intro_text = f"<b>Olá</b> {user_name}! Bem-vindo ao <b>{VPN_NOMBRE} PAY</b>⚡️\n\nSou um bot que recebe pagamentos automáticos para nossa\n\n<b>VPN {VPN_NOMBRE}</b>⚡️\n\n<b>Como posso te ajudar hoje? ☄️</b>"
    bot.send_message(message.from_user.id, intro_text, reply_markup=markup, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == 'gerar_teste')
def generar_teste(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_confirmar = types.InlineKeyboardButton("Sim, gerar teste 📮", callback_data='realizar_teste')
    btn_regresar = types.InlineKeyboardButton("Voltar ao inicio 🔙", callback_data='voltar_inicio')
    markup.add(btn_confirmar, btn_regresar)
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="<b>¿Quer criar uma conta de teste? ⭐️</b>", reply_markup=markup, parse_mode='HTML')
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'realizar_teste')
def realizar_teste(call):
    chat_id = str(call.message.chat.id)
    user_name = user_names.get(chat_id, "Desconocido")
    now = datetime.now()

    with psycopg2.connect(DATABASE_URL) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT last_created FROM ccld_pay_teste WHERE chat_id = %s", (chat_id,))
        row = cursor.fetchone()

        if row:
            last_created = row[0]
            if now - last_created < timedelta(days=DIAS_ESPERA):
                bot.send_message(call.message.chat.id, f"Você deve esperar {DIAS_ESPERA} días antes de crear una nueva cuenta ❗️")
                return

        nome = "teste" + ''.join(random.choices(string.digits, k=3))
        passw = ''.join(random.choices(string.ascii_letters + string.digits, k=5))

        # Insertar o actualizar los datos del usuario en la base de datos
        data = (chat_id, user_name, nome, passw, now)
        cursor.execute("""
            INSERT INTO ccld_pay_teste (chat_id, user_name, nome_teste, senha_teste, last_created)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (chat_id) DO UPDATE 
            SET nome_teste = EXCLUDED.nome_teste, senha_teste = EXCLUDED.senha_teste, last_created = EXCLUDED.last_created
        """, data)
        conn.commit()
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER_IP, port=SERVER_PORT, username=ROOT_USER, password=ROOT_PASS)

    commands = [
        f"useradd -M -s /bin/false {nome}",
        f"echo {nome}:{passw} | chpasswd",
        f"chmod +x /etc/SSHPlus/userteste/{nome}.sh",
        f"at -f /etc/SSHPlus/userteste/{nome}.sh now + {TEMPO_TES} min"
    ]

    for command in commands:
        ssh.exec_command(command)

    message = f"""
    ✅ CONTA TESTE {VPN_NOMBRE}⚡️ CRIADA ✅\n\n
    💡 Dica: Clique no usuário que já copia automaticamente, em seguida cole no app, depois faça o mesmo com a senha!\n\n
    Usuario: `{nome}`
    Senha: `{passw}`\n
    Duração: {TEMPO_TES//60} Horas\n\n
    ⚠️ É necessário abrir o aplicativo com internet para sincronizar as configurações mais recente das operadoras!
    """
    bot.send_message(call.message.chat.id, message, parse_mode='Markdown')

    ssh.close()
 
def create_table_teste():
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ccld_pay_teste (
                    chat_id TEXT PRIMARY KEY,
                    user_name TEXT,
                    nome_teste TEXT,
                    senha_teste TEXT,
                    last_created TIMESTAMP
                )""")
            conn.commit()
    except Exception as e:
        print(f"Error al crear la tabla teste: {e}")

create_table_teste()

@bot.callback_query_handler(func=lambda call: call.data == 'comprar_acesso')
def submenu_comprar(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton(f"1 ACESSO 30 DIAS R${MONTO_1}", callback_data='1_acesso')
    btn2 = types.InlineKeyboardButton(f"2 ACESSOS 30 DIAS R${MONTO_2}", callback_data='2_acessos')
    btn3 = types.InlineKeyboardButton(f"3 ACESSOS 30 DIAS R${MONTO_3}", callback_data='3_acessos')
    btn_voltar = types.InlineKeyboardButton("Voltar ao inicio 🔙", callback_data='voltar_inicio')
    markup.add(btn1, btn2, btn3, btn_voltar)

    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="<b>Escolha o número de acessos que pretende:</b> 🔥", reply_markup=markup, parse_mode='HTML')
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'voltar_inicio')
def menu_principal(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_soporte = types.InlineKeyboardButton("⚙️ SOPORTE", url=f'https://t.me/{NM_USUARIO}')
    btn_comprar = types.InlineKeyboardButton("💎 COMPRAR ACCESSO 💎", callback_data='comprar_acesso')
    btn_descargar_app = types.InlineKeyboardButton(f"BAIXAR {VPN_NOMBRE} 📦", callback_data='descargar_app')
    btn_atualizar_acesso = types.InlineKeyboardButton("ATUALIZAR ACESSOS 🔏", callback_data='atualizar_acesso')
    btn_teste = types.InlineKeyboardButton("GERAR TESTE 🎯", callback_data='gerar_teste')
    markup.add(btn_soporte, btn_comprar, btn_descargar_app, btn_atualizar_acesso, btn_teste)

    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="<b>Você esqueceu alguma coisa? 🚀</b>", reply_markup=markup, parse_mode='HTML')
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data in ['1_acesso', '2_acessos', '3_acessos'])
def seleccion_plan(call):
    if call.data == '1_acesso':
        monto = MONTO_1
    elif call.data == '2_acessos':
        monto = MONTO_2
    elif call.data == '3_acessos':
        monto = MONTO_3

    descripcion_pago = f"<b>Producto:</b> {call.data.replace('_', ' ')} 🎫\n<b>Valor:</b> R${monto} 💰\n<b>Valido:</b> 30 Dias 📝\n<b>Tempo para pago:</b> 15 min 🗯"
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_base64 = types.InlineKeyboardButton("Pagar (Chave Pix)", callback_data=f'pagar_base64_{call.data}')
    btn_qr = types.InlineKeyboardButton("Pagar (QR)", callback_data=f'pagar_qr_{call.data}')
    btn_regresar_plano = types.InlineKeyboardButton("Voltar ao plano 🔙", callback_data='voltar_plano')
    markup.add(btn_base64, btn_qr, btn_regresar_plano)

    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=descripcion_pago, reply_markup=markup, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == 'voltar_plano')
def regresar_a_planos(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton(f"1 ACESSO 30 DIAS R${MONTO_1}", callback_data='1_acesso')
    btn2 = types.InlineKeyboardButton(f"2 ACESSOS 30 DIAS R${MONTO_2}", callback_data='2_acessos')
    btn3 = types.InlineKeyboardButton(f"3 ACESSOS 30 DIAS R${MONTO_3}", callback_data='3_acessos')
    btn_voltar = types.InlineKeyboardButton("Voltar ao inicio 🔙", callback_data='voltar_inicio')
    markup.add(btn1, btn2, btn3, btn_voltar)


    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="<b>Escolha o número de acessos que pretende:</b> 🔥", reply_markup=markup, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == 'renovar_acceso')
def renovar_acceso(call):
    chat_id = call.from_user.id
    msg = bot.send_message(chat_id, "Digite seu nome de usuário SSH para continuar❕\n\n<b>OBSERVAÇÃO:</b> Coloque o nome de usuário exatamente como foi criado ⚪️", parse_mode='HTML')
    bot.register_next_step_handler(msg, process_ssh_username)
 
def process_ssh_username(message):
    username = message.text.strip()
    
    if "teste" in username.lower():  # Convertimos a minúsculas para hacer la comprobación case-insensitive
        bot.send_message(message.chat.id, "Os usuários 'teste' não são válidos para esta função. Tenta de novo ❗️")
        return
    
    client = get_ssh_client(SERVER_IP, SERVER_PORT, ROOT_USER, ROOT_PASS)
    exists, user_details = execute_command(client, f'getent passwd {username}')

    if not exists or 'x' not in user_details:
        bot.send_message(message.chat.id, "O nome de usuário não existe no servidor. Por favor, tente novamente ❌")
        client.close()
        return
   
    number_of_access, days_remaining = get_access_details(username, client) # Obtener la cantidad de accesos y los días restantes para el usuario

    monto = 0
    if number_of_access == 1:
        monto = MONTO_1
    elif number_of_access == 2:
        monto = MONTO_2
    elif number_of_access == 3:
        monto = MONTO_3

    descripcion_pago = f"Renovación de acceso SSH para {username}."

    process_ssh_payment(message, monto, descripcion_pago, number_of_access, days_remaining, username)

    client.close()

def generate_unique_id(monto, descripcion_pago, username):
    unique_id = str(uuid.uuid4())
    payment_info_by_id[unique_id] = {
        'monto': monto,
        'descripcion_pago': descripcion_pago,
        'username': username
    }
    return unique_id

def get_from_db(unique_id):
    result = payment_info_by_id.get(unique_id, (None, None, None))
    return result

def process_ssh_payment(message, monto, descripcion_pago, number_of_access, days_remaining, username):
    try:
        if monto == 0: # Si el valor es cero el cliente tiene más de tres accesos
            bot.send_message(message.chat.id, "O pagamento não pode ser efetuado porque sua conta possui o plano Básico. Você pode renovar seu acesso a uma conta premium entrando em contato com o Proprietário 🛑")
            return

        info_message = (f"Você tem {number_of_access} acessos e {days_remaining} días restantes 💭\n\n"
                        f"O valor da renovação será R${monto} por mais 30 días de acceso 🔖\n\n"
                        f"¿Deseja gerar o pagamento ⁉️")

        markup = types.InlineKeyboardMarkup()
        unique_id = generate_unique_id(monto, descripcion_pago, username)
        markup.add(types.InlineKeyboardButton('Sim, gerar pagamento 💠', callback_data=f'generate_payment:{unique_id}'))
        bot.send_message(message.chat.id, info_message, reply_markup=markup)
    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(message.chat.id, "¡Opa! Ocurrió un error en el bot.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('generate_payment'))
def generate_payment(call):
    try:
        _, unique_id = call.data.split(":")
        
        payment_info = get_from_db(unique_id)
        
        monto = int(payment_info.get('monto', 0)) 
        descripcion_pago = payment_info.get('descripcion_pago', None)
        username = payment_info.get('username', None)

        if 10 <= monto <= 100:
            id_p, qr_code_data = create_ssh_payment(monto, descripcion_pago, str(call.message.chat.id), username)
            user = bot.get_chat_member(call.message.chat.id, call.from_user.id)
            user_name = user.user.first_name + " " + (user.user.last_name or "")
            
            bot.send_message(call.message.chat.id, "Gerando pagamento...")

            pix_key = f"<code>{qr_code_data}</code>"
            info_message = (f"¡{user_name} sua ordem de pagamento foi criada com sucesso!⚡️\n\n"
                            f"Este es su ID de pago: {id_p}\n\n"
                            f"Lembre-se de que você só tem 10 min para concluir o pagamento ✨\n\n"
                            f"Após efetuar o pagamento enviar o recibo ao <a href='https://t.me/{NM_USUARIO}'>Dono</a>📞\n\n"
                            f"Chave Pix (base64):💠\n\n{pix_key}")
            
            bot.send_message(call.message.chat.id, info_message, parse_mode='HTML', disable_web_page_preview=True)

            qr = qrcode.make(qr_code_data)
            qr_img_buffer = BytesIO()
            qr.save(qr_img_buffer, format="PNG")
            qr_img_buffer.seek(0)
            bot.send_photo(call.message.chat.id, qr_img_buffer)
            
            notify_payment_status(id_p, call.message.chat.id)
            insert_payment(id_p, str(call.message.chat.id), user_name, username)
        else:
            bot.send_message(call.message.chat.id, "Quantidade fora da faixa permitida. Normalmente, esse erro ocorre porque você não é um usuário SSH personalizado.")
    except ValueError as ve:
        print(f"Error de valor: {ve}")
        bot.send_message(call.message.chat.id, "¡Opa! Ocurrió un error en el bot.")
    except Exception as e:
        print(f"Error general: {e}")
        bot.send_message(call.message.chat.id, "¡Opa! Ocurrió un error en el bot.")
 
def notify_payment_status(id_p, chat_id):  # Para la renovación
    is_approved = status(id_p)

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        now = datetime.now()
        
        if is_approved == True:
            cursor.execute("SELECT username, user_name FROM ccld_pay_renovacion WHERE id_p=%s", (id_p,))
            row = cursor.fetchone()
            username = row[0]
            user_name = row[1]

            client = get_ssh_client(SERVER_IP, SERVER_PORT, ROOT_USER, ROOT_PASS)
            extend_msg = extend_ssh_user_expiration(client, username, days=31)
            
            mensaje_canal = (f"¡El usuario de <code>{user_name}</code> ha actualizado su acceso: <code>{username}</code> 🎉 "
                                            f"y también su ID de mercado pago: <code>{id_p}</code>")
                                 
            bot.send_message(TELEGRAM_CHANNEL, mensaje_canal, parse_mode='HTML', disable_web_page_preview=True)
            
            info_message = (f"<b>¡Seu processo de renovação foi concluído com sucesso.!💫</b>\n\n"
                            f"Este é o seu ID de pagamento: <code>{id_p}</code> ✨\n\n"
                            f"Agora você pode levar o recibo ao <a href='https://t.me/{NM_USUARIO}'>Dono</a> para segurança e backup de seus pagamentos 🔓\n\n"
                            f"{extend_msg}")
            
            bot.send_message(chat_id, info_message, parse_mode='HTML', disable_web_page_preview=True)
            
            cursor.execute("""
                UPDATE ccld_pay_renovacion
                SET hora_final = %s,
                    estado_pago = 'Aprobado'
                WHERE id_p = %s
            """, (now.strftime("%H:%M:%S"), id_p))
            conn.commit()
        
        elif is_approved == False:
            mensaje_cliente = (f"Seu renovação foi cancelado por não ser feito a tempo ❌\n\n"
                               f"Se você acha que isso é um bug, entre em contato com o <a href='https://t.me/{NM_USUARIO}'>suporte</a>⚙️\n\n"
                               f"ID de MP: <code>{id_p}</code>\n")
            bot.send_message(chat_id, mensaje_cliente, parse_mode='HTML', disable_web_page_preview=True)
            
            cursor.execute("""
                UPDATE ccld_pay_renovacion
                SET hora_final = %s,
                    estado_pago = 'Cancelado'
                WHERE id_p = %s
            """, (now.strftime("%H:%M:%S"), id_p))
            conn.commit()
        
        else:
            bot.send_message(chat_id, "Ocorreu um erro ao verificar o status do pagamento 🔴")
        
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        if conn:
            cursor.close()
            conn.close()

def create_table_renovacion():
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ccld_pay_renovacion (
                    id_p TEXT,
                    chat_id TEXT,
                    user_name TEXT,
                    username TEXT,
                    fecha TEXT,
                    hora TEXT,
                    hora_final TEXT,
                    estado_pago TEXT
                )""")
            conn.commit()
    except Exception as e:
        print(f"Error al crear la tabla renovación: {e}")

def insert_payment(id_p, chat_id, user_name, username):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM ccld_pay_renovacion WHERE id_p=%s AND username=%s", (id_p, username,)) # Verifica si el id_p y username ya existen
        if cursor.fetchone() is None:
            now = datetime.now()
            fecha = now.strftime("%Y-%m-%d")
            hora = now.strftime("%H:%M:%S")

            cursor.execute("""
                INSERT INTO ccld_pay_renovacion (id_p, chat_id, user_name, username, fecha, hora) 
                VALUES (%s, %s, %s, %s, %s, %s)
                """, (id_p, chat_id, user_name, username, fecha, hora))
        
            conn.commit()
    except Exception as e:
        print(f"Error al insertar el pago: {e}")
    finally:
        if conn:
            cursor.close()
            conn.close()

create_table_renovacion()

def create_ssh_payment(value, description, chat_id, username):
    monto = float(str(value)+'.00')
    descripcion_pago = description
    user_email = f"{chat_id}@ccldpay.com"
    user = bot.get_chat_member(chat_id, chat_id)
    user_name = user.user.first_name + " " + (user.user.last_name or "")
    sdk = mercadopago.SDK(MERCADO_PAGO_TOKEN)
    payment_data = {
        "transaction_amount": monto,
        "description": descripcion_pago,
        "payment_method_id": "pix",
        "payer": {
            "email": user_email,
            "first_name": user_name.split()[0],
            "last_name": user_name.split()[1] if len(user_name.split()) > 1 else '',
            "identification": {"type": "CPF", "number": ''},
            "address": {
                "zip_code": '', "street_name": '', "street_number": '', "neighborhood": '', "city": '', "federal_unit": ''
            }
        }
    }
    payment_response = sdk.payment().create(payment_data)
    if payment_response is None or "response" not in payment_response:
        return None
    payment = payment_response["response"]
    id_p = str(payment["id"])
    pix = payment['point_of_interaction']['transaction_data']['qr_code']
    insert_payment(id_p, chat_id, user_name, username)
    return id_p, pix
    
def expiration():
    with open('./config.json', 'r') as file:
        config = json.loads(file.read())
        expiration_payment = config['expiration_payment_in_minutes']
    
    time_change = datetime.timedelta(minutes=int(expiration_payment))
    new_time = datetime.datetime.now() + time_change

    tz = pytz.timezone("America/Bahia")
    aware_dt = tz.localize(new_time)

    a = aware_dt.isoformat()
    
    return a[:23]+a[26:]

def status(id_a):
    try:
        with open('./config.json', 'r') as file:
            config = json.load(file)

        expiration_payment = config['expiration_payment_in_minutes']
        headers = {"Authorization": f"Bearer {MERCADO_PAGO_TOKEN}"}
        contador = 0
        while True:
            contador += 1
            
            request = requests.get(f'https://api.mercadopago.com/v1/payments/{id_a}', headers=headers).json()
            status = str(request['status']).strip()
            if not contador > int(expiration_payment):
                if status == 'pending':
                    pass
                    
                elif status == 'approved':
                    r = 1
                    break
                
                time.sleep(60)
                
            else:
                r = 0
                break

        if r == 1:
            return True
        
        else:
            return False

    except Exception as e:
        print(f"Error al verificar el estado del pago: {e}")
        return 'Erro'

@bot.callback_query_handler(func=lambda call: call.data.startswith('pagar_base64_') or call.data.startswith('pagar_qr_'))
def opcion_pago(call):
    try:
        chat_id = call.message.chat.id
        nombre_cliente = user_names.get(chat_id, "Usuario desconocido")       
        plan_selected = call.data.replace('pagar_base64_', '').replace('pagar_qr_', '') # Identificar el plan seleccionado por el usuario.
        monto, description = get_payment_details(plan_selected)
        payment = create_payment(monto, description, str(call.message.chat.id))
        if not payment:
            raise Exception("Failed to create payment.")
            
        payment_id = payment['response']['id']
        add_mapping(payment_id, str(call.message.chat.id), monto, nombre_cliente)

        qr_code_data = payment['response']['point_of_interaction']['transaction_data']['qr_code']

        if call.data.startswith('pagar_base64_'):
            bot.send_message(call.message.chat.id, f"Chave Pix (base64):💠\n\n<code>{qr_code_data}</code>", parse_mode='HTML')
        else:
            send_qr_code(call.message.chat.id, qr_code_data)
    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(call.message.chat.id, "¡Opa! Ocorreu um erro no bot.")
        
def get_payment_details(plan):
    if plan == '1_acesso':
        return MONTO_1, "1 ACESSO 30 DIAS"
    elif plan == '2_acessos':
        return MONTO_2, "2 ACESSOS 30 DIAS"
    elif plan == '3_acessos':
        return MONTO_3, "3 ACESSOS 30 DIAS"
    else:
        raise ValueError("Plan desconocido.")

def send_qr_code(chat_id, data):
    qr = qrcode.make(data)
    qr_img_buffer = BytesIO()
    qr.save(qr_img_buffer)  # Elimina el argumento "format"
    qr_img_buffer.seek(0)
    bot.send_photo(chat_id, qr_img_buffer)

def is_payment_in_renovacion_table(payment_id):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ccld_pay_renovacion WHERE id_p=%s", (payment_id,))
        if cursor.fetchone() is not None:
            return True
        else:
            return False
    except Exception as e:
        print(f"Error al consultar la tabla de renovación: {e}")
        return False
    finally:
        if conn:
            cursor.close()
            conn.close()

@web_server.route('/mercadopago-webhook', methods=['POST'])
def mercadopago_webhook():
    data = request.json
    event_type = data.get('type')
    event_action = data.get('action')
    
    if not (event_type and event_action):
        print("Evento o acción no proporcionados en la notificación.")
        return jsonify({"status": "received but not processed", "message": "Event type or action not provided."}), 200

    payment_id = data.get('data', {}).get('id')
    if not payment_id:
        print("No se pudo obtener el payment_id.")
        return jsonify({"status": "received but not processed", "message": "No payment_id found"}), 200
        
    if is_payment_in_renovacion_table(payment_id): # Comprueba si el ID de mercado pago existe en la tabla ccld_pay_renovacion para no hacer nada
        return jsonify({"status": "received but not processed", "message": f"Payment_id {payment_id} found in renovacion table"}), 200

    if event_type == 'payment':
        if event_action == 'payment.created':
            handle_payment_created(payment_id)
        elif event_action == 'payment.updated':
            process_updated_payment(payment_id)
    else:
        print(f"Evento {event_type} con acción {event_action} no manejado.")
        return jsonify({"status": "received but not processed", "message": f"Unhandled event: {event_type} with action: {event_action}"}), 200

    return jsonify({"status": "received"}), 200

def process_updated_payment(payment_id):
    payment_details = get_payment_details_from_mercadopago(payment_id)

    if not payment_details:
        print(f"No se pudieron obtener detalles para el payment_id: {payment_id}")
        return

    status = payment_details.get('status')   
    # Basado en el estado (status) del pago, decide el bot como proceder
    if status == 'approved':
        handle_payment_approved(payment_id)
    elif status == 'pending':
        handle_payment_pending(payment_id)
    elif status == 'rejected':
        handle_payment_rejected(payment_id)
    elif status == 'created':
        handle_payment_created(payment_id)
    elif status == 'cancelled':
        handle_payment_cancelled(payment_id)
    else:
        print(f"Estado de pago no manejado: {status} para payment_id: {payment_id}")

def get_payment_details_from_mercadopago(payment_id):
    try:
        payment_info = sdk.payment().get(payment_id)
        if payment_info and 'response' in payment_info:
            return payment_info['response']
        else:
            print(f"Error al obtener detalles del pago para payment_id: {payment_id}")
            return None
    except Exception as e:
        print(f"Error al obtener detalles del pago. Error: {str(e)}")
        return None

def map_amount_to_ssh_limit(monto):
    if monto == MONTO_1:
        return 1
    elif monto == MONTO_2:
        return 2
    elif monto == MONTO_3:
        return 3
    else:
        return 0 

def handle_payment_approved(payment_id):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute("SELECT telegram_chat_id, monto, nombre_cliente FROM ccld_pay_compra WHERE mp_user_id = %s", (payment_id,))
        result = cursor.fetchone()
        
        if result:
            chat_id, monto, nombre_cliente = result
            
            sshlimiter = 0
            if monto == MONTO_1:
                sshlimiter = 1
            elif monto == MONTO_2:
                sshlimiter = 2
            elif monto == MONTO_3:
                sshlimiter = 3

            username = generate_username()
            password = generate_password()
            
            try:
                ssh_client = get_ssh_client(SERVER_IP, SERVER_PORT, ROOT_USER, ROOT_PASS)
                create_ssh_user_on_remote(ssh_client, username, password, sshlimiter)
                ssh_client.close()
                
                cursor.execute("UPDATE ccld_pay_compra SET ssh_username = %s, ssh_password = %s WHERE mp_user_id = %s", (username, password, payment_id))
                conn.commit()
                
                mensaje_canal = (f"O pagamento de {nombre_cliente} foi confirmado e sua conta SSH foi criada! 🎉\n\n"
                                 f"Cliente: <code>{nombre_cliente}</code>\n"
                                 f"Hostname: {SERVER_IP}\n"
                                 f"Username: <code>{username}</code>\n"
                                 f"Password: <code>{password}</code>\n\n"
                                 f"ID de MP: <code>{payment_id}</code>\n"
                                 f"Valor: R${monto}")
                bot.send_message(TELEGRAM_CHANNEL, mensaje_canal, parse_mode='HTML', disable_web_page_preview=True)
                
                bot.send_message(chat_id, 
                    f"<b>¡Seu processo de pagamento foi concluído com sucesso!💫</b>\n\n\n"
                    f"Este é o seu ID de pagamento: <code>{payment_id}</code> ✨\n\n\nSeu nome de usuário SSH é: <code>{username}</code> 📌\n\n\n"
                    f"Agora você pode levar o recibo ao <a href='https://t.me/{NM_USUARIO}'>Dono</a> e liberar sua senha "
                    f"ou você pode ir diretamente para atualizar o acesso no menu principal e alterar a senha apenas com seu nome de usuário SSH 🔓\n\n\n"
                    f"‼️Você pode falar com o <a href='https://t.me/{NM_USUARIO}'>Dono</a> se precisar de uma conta personalizada‼️", 
                    parse_mode='HTML', disable_web_page_preview=True)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"Error al crear la cuenta SSH: {str(e)}")
                error_msg = f"Error al crear la cuenta SSH: {str(e)}"
                print(error_msg)
                bot.send_message(chat_id, error_msg, parse_mode='Markdown', disable_web_page_preview=True)
                bot.send_message(TELEGRAM_CHANNEL, error_msg, parse_mode='Markdown', disable_web_page_preview=True)
        else:
            print(f"No se encontró un chat_id para el payment_id: {payment_id} approved")
    except Exception as e:
        print(f"Error al acceder a la base de datos: {e}")

def handle_payment_pending(payment_id):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        cursor.execute("SELECT telegram_chat_id, monto FROM ccld_pay_compra WHERE mp_user_id = %s", (payment_id,))
        result = cursor.fetchone()

        if result:
            chat_id, monto = result
            mensaje_usuario = (f"Seu pagamento está pendente de revisão 🕒\n\n"
                               f"Só precisa esperar, se demorar mais de 24 horas, entre em contato primeiro com seu banco e depois com o suporte CCLD⚡️\n\n"
                               f"ID do MP: {payment_id}\n"
                               f"Valor: R${monto}")

            mensagem_canal = f"O pagamento com o ID {payment_id} ainda está pendente."
            bot.send_message(chat_id, mensaje_usuario, parse_mode='Markdown', disable_web_page_preview=True)
            bot.send_message(TELEGRAM_CHANNEL, mensaje_canal, parse_mode='Markdown', disable_web_page_preview=True)
        else:
            print(f"No se encontró un chat_id para el payment_id: {payment_id} pending")
    except Exception as e:
        print(f"Error al acceder a la base de datos: {e}")

def handle_payment_rejected(payment_id):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute("SELECT telegram_chat_id, monto FROM ccld_pay_compra WHERE mp_user_id = %s", (payment_id,))
        result = cursor.fetchone()
        
        if result:
            chat_id, monto = result

            mensaje = (f"Seu pagamento foi recusado ❌\n\n"
                       f"Verifique sua forma de pagamento e tente novamente❗️\n\n"
                       f"Se você acha que foi um bug e tem um recibo válido criado em menos de 6 horas, entre em contato com o [suporte](https://t.me/{NM_USUARIO})⚙️"
                       f"ID de MP: {payment_id}\n"
                       f"Valor: R${monto}")
            
            bot.send_message(chat_id, mensaje, parse_mode='Markdown', disable_web_page_preview=True)
            bot.send_message(TELEGRAM_CHANNEL, mensaje, parse_mode='Markdown', disable_web_page_preview=True)
        else:
            print(f"No se encontró un chat_id para el payment_id: {payment_id} rejected")
    except Exception as e:
        print(f"Error al acceder a la base de datos: {e}")
            
def handle_payment_cancelled(payment_id):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute("SELECT telegram_chat_id, monto FROM ccld_pay_compra WHERE mp_user_id = %s", (payment_id,))
        result = cursor.fetchone()

        if result:
            chat_id, monto = result

            mensaje_cliente = (f"Seu pagamento foi cancelado por não ser feito a tempo ❌\n\n"
                               f"Se você acha que isso é um bug, entre em contato com o <a href='https://t.me/{NM_USUARIO}'>suporte</a>⚙️\n\n"
                               f"ID de MP: <code>{payment_id}</code>\n"
                               f"Valor: R${monto}")

            mensaje_canal = f"O pagamento com o ID do Mercado Pago: <code>{payment_id}</code> foi cancelado devido ao não pagamento dentro do prazo."

            bot.send_message(chat_id, mensaje_cliente, parse_mode='HTML', disable_web_page_preview=True)
            bot.send_message(TELEGRAM_CHANNEL, mensaje_canal, parse_mode='HTML', disable_web_page_preview=True)
        else:
            print(f"No se encontró un chat_id para el payment_id: {payment_id} cancelled")
    except Exception as e:
        print(f"Error al acceder a la base de datos: {e}")

def handle_payment_created(payment_id):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute("SELECT telegram_chat_id, monto, nombre_cliente FROM ccld_pay_compra WHERE mp_user_id = %s", (payment_id,))
        result = cursor.fetchone()

        if result:
            chat_id, monto, nombre_cliente = result

            mensaje = (f"¡Sua ordem de pagamento foi criada com sucesso!⚡️\n\nCom o ID: <code>{payment_id}</code> e valor: R${monto} ✍🏻\n\n"
                       f"Lembre-se de que você só tem um tempo limitado para concluir o pagamento ✨\n\n"
                       f"Após efetuar o pagamento enviar o recibo ao <a href='https://t.me/{NM_USUARIO}'>Dono</a>📞")
            
            bot.send_message(chat_id, mensaje, parse_mode='HTML', disable_web_page_preview=True)
            bot.send_message(TELEGRAM_CHANNEL, f"O pagamento com o ID de MP: <code>{payment_id}</code> e o valor: R${monto} foi criado. 🟠", parse_mode='HTML')
        else:
            print(f"No se encontró un chat_id para el payment_id: {payment_id} created")
    except Exception as e:
        print(f"Error al acceder a la base de datos: {e}")

def create_table():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ccld_pay_compra (
            mp_user_id TEXT PRIMARY KEY,
            telegram_chat_id BIGINT,
            monto INTEGER,
            nombre_cliente TEXT,
            ssh_username TEXT,
            ssh_password TEXT,
            last_changed_date TEXT,
            last_changed_time TEXT,
            change_count INTEGER
        )
        ''')

        conn.commit()

    except Exception as e:
        print(f"Error al conectar con la base de datos: {e}")
        
def update_password_and_tracking(ssh_username, new_password):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM ccld_pay_compra WHERE ssh_username=%s", (ssh_username,))
        if cursor.fetchone() is None:
            return

        now = datetime.now()
        fecha = now.strftime("%Y-%m-%d")
        hora = now.strftime("%H:%M:%S")

        cursor.execute("SELECT change_count FROM ccld_pay_compra WHERE ssh_username = %s", (ssh_username,))
        row = cursor.fetchone()
        if row:
            change_count = row[0] if row[0] else 0
        else:
            print("Usuario no encontrado.")
            return

        query = """
        UPDATE ccld_pay_compra
        SET ssh_password = %s,
            last_changed_date = %s,
            last_changed_time = %s,
            change_count = %s
        WHERE ssh_username = %s
        """
        cursor.execute(query, (new_password, fecha, hora, change_count + 1, ssh_username))
        conn.commit()

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            cursor.close()
            conn.close()

def add_mapping(mp_user_id, telegram_chat_id, monto, nombre_cliente):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        query = "INSERT INTO ccld_pay_compra (mp_user_id, telegram_chat_id, monto, nombre_cliente) VALUES (%s, %s, %s, %s)"  # Y aquí también
        cursor.execute(query, (mp_user_id, telegram_chat_id, monto, nombre_cliente))

        conn.commit()

    except Exception as e:
        print(f"Error al agregar mapeo: {e}")
        
def get_telegram_id(mp_user_id):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute("SELECT telegram_chat_id FROM ccld_pay_compra WHERE mp_user_id = %s", (mp_user_id,))
        
        result = cursor.fetchone()
        if result:
            telegram_chat_id = result[0]
            print(f"Obtenido telegram_chat_id={telegram_chat_id} para mp_user_id={mp_user_id}")
            return telegram_chat_id
        else:
            print(f"No se encontró ningún resultado en la base de datos para mp_user_id={mp_user_id}")
            return None
    except Exception as e:
        print(f"Error al acceder a la base de datos: {e}")
        return None

def get_chat_id_from_database(payment_id):
    try:
        chat_id = get_telegram_id(payment_id)
        if chat_id:
            return chat_id
        else:
            print("No se pudo obtener el chat_id de la base de datos.")
            return None
    except Exception as e:
        print(f"Error al obtener chat_id de la base de datos: {e}")
        return None
        
def fetch_all_mappings():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ccld_pay_compra")
        mappings = cursor.fetchall()
        return mappings
    except Exception as e:
        print(f"Error al buscar todos los mapeos: {e}")
        return None

create_table()

if __name__ == "__main__":
    print("CCLD PAY Iniciando el bot...\nEsta es la URL que tienes que copiar y colocar en Webhook de Mercado Pago")
    print("URL NGROK: https://TU_URL_NGROK_ABAJO_DE_ESTO/mercadopago-webhook")
    conf.get_default().config_path = "./config_ngrok.yml"
    conf.get_default().region = "sa"
    ngrok.set_auth_token(NGROK_TOKEN)
    ngrok_tunel = ngrok.connect(5000, bind_tls=True)
    ngrok_url = ngrok_tunel.public_url
    print("URL NGROK:", ngrok_url)
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=ngrok_url)
    serve(web_server, host="0.0.0.0", port=5000)