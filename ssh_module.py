import json
import string
import random
import requests
import paramiko
from datetime import datetime, timedelta

def generate_username():
    number = random.randint(100, 999)
    return f"Net{number}"

def generate_password():
    numbers = ''.join(random.choice(string.digits) for _ in range(3))
    letter = random.choice(string.ascii_letters)
    return numbers + letter

def get_ssh_client(host, port, username, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port, username, password)
    return client

def create_ssh_user_on_remote(client, new_username, new_password, sshlimiter):
    try:
        dias = 31 # Calcular la fecha de caducidad
        final = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
        
        if not execute_command(client, f'sudo useradd -e {final} -M -s /bin/false {new_username}'):
            return "Error al crear el usuario."
        
        if not execute_command(client, f'echo "{new_username}:{new_password}" | sudo chpasswd'):
            return "Error al establecer la contraseña."
        
        if not execute_command(client, f'echo "{new_password}" | sudo tee -a /etc/SSHPlus/senha/{new_username}'):
            return "Error al guardar la contraseña."
        
        if not execute_command(client, f'echo "{new_username} {sshlimiter}" | sudo tee -a /root/usuarios.db'):
            return "Error al añadir el usuario a usuarios.db"
        
        return "Usuario creado con éxito."
    finally:
        client.close()

def change_ssh_user_password(client, username, new_password):
    try:
        if new_password == '/start':
            return "'/start' não é permitido como senha 🛑"

        exists, output = execute_command(client, f'getent passwd {username}')

        if not exists or username not in output:
            return "O usuário não existe, a senha não pode ser alterada ‼️"

        if not execute_command(client, f'echo "{username}:{new_password}" | sudo chpasswd'):
            return "Erro ao alterar a senha."

        if not execute_command(client, f'echo "{new_password}" | sudo tee /etc/SSHPlus/senha/{username}'):
            return "Erro ao atualizar a senha no arquivo."

        return "Senha alterada com sucesso ✅"
    finally:
        client.close()
     
def extend_ssh_user_expiration(client, username, days=31):
    try:
        exists, _ = execute_command(client, f'getent passwd {username}')

        if not exists:
            return "O usuário não existe, a expiração não pode ser estendida"

        new_expire_date = datetime.now() + timedelta(days=days)
        new_expire_date_str = new_expire_date.strftime('%Y-%m-%d')

        if not execute_command(client, f'sudo chage -E {new_expire_date_str} {username}'):
            return f"Falha ao estender a expiração da conta para {new_expire_date_str}."

        if not execute_command(client, f'sudo chage -d $(date +%Y-%m-%d) -M {days} {username}'):
            return f"Falha ao estender a expiração da senha para {days} dias."

        return f"Expiração da conta e da senha estendidas para {new_expire_date_str} e {days} dias, respectivamente."
    finally:
        client.close()

def parse_number_of_access_from_comment(comment):
    
    if "1 access" in comment:
        return 1
    elif "2 access" in comment:
        return 2
    elif "3 access" in comment:
        return 3
    else:
        return 0
        
def execute_command(client, command):
    stdin, stdout, stderr = client.exec_command(command)
    output = stdout.read().decode().strip()
    err = stderr.read().decode()
    if err:
        print(f"Error al ejecutar '{command}': {err}")
        return False, ""
    return True, output

def get_number_of_access(username, client, path="/root/usuarios.db"):
    command = f'grep "^{username} " {path}' # Buscar líneas que comiencen con el nombre de usuario seguido de un espacio
    success, output = execute_command(client, command)
    if not success or not output:
        print(f"Error al obtener el número de accesos para el usuario {username} en {path}.")
        return 0
        
    number_of_access = int(output.split()[1])

    return number_of_access

def get_days_remaining(username, client):
    command = f'sudo chage -l {username} | grep "Account expires" | cut -d: -f2'
    success, output = execute_command(client, command)

    if not success:
        print(f"Error al obtener la fecha de expiración para el usuario {username}.")
        return 0
        
    expiration_date_str = output.strip()

    if expiration_date_str == "never":
        return "nunca"
    else:
        expiration_date = datetime.strptime(expiration_date_str, "%b %d, %Y")
        remaining_days = (expiration_date - datetime.now()).days
        return remaining_days

def get_access_details(username, client):
    number_of_access = get_number_of_access(username, client)

    days_remaining = get_days_remaining(username, client)

    return number_of_access, days_remaining

def parse_days_remaining_from_output(output):
    days_remaining_str = output.strip()
    if days_remaining_str == "never":
        return "nunca"
    else:
        from datetime import datetime
        expiration_date = datetime.strptime(days_remaining_str, "%b %d, %Y")
        remaining_days = (expiration_date - datetime.now()).days
        return remaining_days
