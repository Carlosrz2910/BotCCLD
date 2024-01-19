#!/bin/bash

# Actualizar repositorios
echo "Actualizando repositorios..."
apt update
apt upgrade -y

# Preguntar si desea instalar el bot
read -p "¿Desea instalar el bot? (yes/no): " install_bot

if [ "$install_bot" != "yes" ]; then
    echo "Continuando sin instalar el bot."
else
    # Descargar e instalar Python 3.11
    echo "Descargando Python 3.11..."
    wget https://www.python.org/ftp/python/3.11.0/Python-3.11.0.tgz
    tar -xf Python-3.11.0.tgz
    cd Python-3.11.0
    ./configure --enable-optimizations
    make
    make altinstall

    # Instalar Python 3.11
    echo "Instalando Python 3.11..."
    apt install -y python3.11 python3.11-dev
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

    # Instalar PostgreSQL y libpq-dev
    echo "Instalando PostgreSQL y libpq-dev..."
    apt install -y postgresql libpq-dev

    # Preguntar y cambiar nombre y contraseña de PostgreSQL
    read -p "Ingresa el nuevo nombre de usuario de PostgreSQL: " postgres_user
    read -p "Ingresa la nueva contraseña de PostgreSQL: " postgres_password

    sudo -u postgres psql -c "ALTER USER $postgres_user WITH ENCRYPTED PASSWORD '$postgres_password';"

    # Generar link de PostgreSQL
    postgres_link="postgres://$postgres_user:$postgres_password@localhost/ejemplo"

    # Alterar datos en el archivo .json
    sed -i "s|\"DATABASE_URL\":.*|\"DATABASE_URL\": \"$postgres_link\",|" archivo.json

    # Descargar y extraer el archivo .zip del repositorio
    wget https://tu-repositorio.com/CCLD.zip
    unzip CCLD.zip

    # Instalar dependencias y librerías
    apt install tmux -y
    python3.11 -m pip install Flask pyngrok psycopg2 requests telebot qrcode waitress mercadopago uuid pytz Pillow==8.0.0

    # Preguntar al usuario las credenciales
    read -p "Ingrese el nuevo TOKEN: " TOKEN
    read -p "Ingrese el nuevo NGROK_TOKEN: " NGROK_TOKEN
    # Continuar con todas las demás credenciales

    # Actualizar el archivo .json con las nuevas credenciales
    cat <<EOL >archivo.json
{
    "TOKEN": "$TOKEN",
    "NGROK_TOKEN": "$NGROK_TOKEN",
    // Continuar con todas las demás credenciales
}
EOL

    # Iniciar el bot en segundo plano con tmux
    tmux new-session -d -s bot_session 'python3.11 CCLD.py'

    echo "Bot instalado y configurado correctamente."

else
    echo "No se ha instalado el bot."
fi