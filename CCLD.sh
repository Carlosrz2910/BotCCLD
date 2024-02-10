#!/bin/bash

# Actualizar repositorios y paquetes
echo "Actualizando repositorios..."
sudo apt update && sudo apt upgrade -y

# Definir variables predeterminadas o leer desde el entorno
install_bot=${INSTALL_BOT:-yes} # Cambiar a "no" para deshabilitar la instalación automática
postgres_user=${POSTGRES_USER:-postgres_user} # Establecer nombre de usuario de PostgreSQL
postgres_password=${POSTGRES_PASSWORD:-ChangeMe} # Establecer contraseña de PostgreSQL
TOKEN=${TOKEN:-YourTokenHere} # Token de tu bot
NGROK_TOKEN=${NGROK_TOKEN:-YourNgrokTokenHere} # Token de Ngrok

if [ "$install_bot" != "yes" ]; then
    echo "Instalación del bot deshabilitada."
    exit 0
fi

echo "Instalando dependencias necesarias..."
sudo apt-get install -y wget build-essential checkinstall libreadline-gplv2-dev libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev postgresql libpq-dev tmux unzip

# Descargar e instalar Python 3.11 desde el código fuente
echo "Descargando e instalando Python 3.11..."
wget https://www.python.org/ftp/python/3.11.0/Python-3.11.0.tgz
tar -xf Python-3.11.0.tgz
cd Python-3.11.0
./configure --enable-optimizations
make -j $(nproc)
sudo make altinstall
cd ..

# Configurar PostgreSQL
echo "Configurando PostgreSQL..."
sudo -u postgres psql -c "CREATE USER $postgres_user WITH PASSWORD '$postgres_password';"
sudo -u postgres psql -c "CREATE DATABASE ejemplo OWNER $postgres_user;"

# Generar link de PostgreSQL
postgres_link="postgres://$postgres_user:$postgres_password@localhost/ejemplo"
# Alterar datos en el archivo .json
sed -i "s|\"DATABASE_URL\":.*|\"DATABASE_URL\": \"$postgres_link\",|" archivo.json

# Descargar y preparar el bot
echo "Preparando el bot..."
wget https://tu-repositorio.com/CCLD.zip
unzip CCLD.zip
/usr/local/bin/python3.11 -m pip install -r requirements.txt # Asumiendo que tienes un archivo requirements.txt

# Configurar archivo .json con credenciales
echo "Configurando credenciales..."
cat <<EOL >archivo.json
{
    "TOKEN": "$TOKEN",
    "NGROK_TOKEN": "$NGROK_TOKEN"
    // Añadir aquí el resto de credenciales necesarias
}
EOL

# Iniciar el bot en segundo plano con tmux
echo "Iniciando el bot..."
tmux new-session -d -s bot_session '/usr/local/bin/python3.11 CCLD.py'

echo "Bot instalado y configurado correctamente."
