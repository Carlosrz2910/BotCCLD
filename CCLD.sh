#!/bin/bash

# Actualizar repositorios y paquetes
echo "Actualizando repositorios..."
sudo apt update && sudo apt upgrade -y

# Preguntar si desea instalar el bot
read -p "¿Desea instalar el bot? (yes/no): " install_bot

if [ "$install_bot" != "yes" ]; then
    echo "Continuando sin instalar el bot."
    exit 0
fi

# Descargar e instalar Python 3.11 desde el código fuente
echo "Descargando Python 3.11..."
wget https://www.python.org/ftp/python/3.11.0/Python-3.11.0.tgz
tar -xf Python-3.11.0.tgz
cd Python-3.11.0
./configure --enable-optimizations
make -j $(nproc)
sudo make altinstall

# Instalar PostgreSQL y libpq-dev
echo "Instalando PostgreSQL y libpq-dev..."
sudo apt install -y postgresql libpq-dev

# Preguntar y cambiar nombre y contraseña de PostgreSQL
read -p "Ingresa el nuevo nombre de usuario de PostgreSQL: " postgres_user
read -p "Ingresa la nueva contraseña de PostgreSQL: " postgres_password

# Crear usuario de PostgreSQL si no existe
sudo -u postgres psql -c "DO \\
\$do\$ \\
BEGIN \\
   IF NOT EXISTS ( \\
      SELECT FROM pg_catalog.pg_user \\
      WHERE  usename = '$postgres_user') THEN \\
      CREATE ROLE "$postgres_user" LOGIN PASSWORD '$postgres_password'; \\
   END IF; \\
END \\
\$do\$;"

# Generar link de PostgreSQL
postgres_link="postgres://$postgres_user:$postgres_password@localhost/ejemplo"

# Alterar datos en el archivo .json
sed -i "s|\"DATABASE_URL\":.*|\"DATABASE_URL\": \"$postgres_link\",|" archivo.json

# Descargar y extraer el archivo .zip del repositorio
wget https://tu-repositorio.com/CCLD.zip
unzip CCLD.zip

# Instalar tmux y dependencias de Python
sudo apt install tmux -y
/usr/local/bin/python3.11 -m pip install Flask pyngrok psycopg2 requests telebot qrcode waitress mercadopago uuid pytz Pillow==8.0.0

# Preguntar al usuario las credenciales
read -p "Ingrese el nuevo TOKEN: " TOKEN
read -p "Ingrese el nuevo NGROK_TOKEN: " NGROK_TOKEN
# Continuar con todas las demás credenciales

# Actualizar el archivo .json con las nuevas credenciales
# Asegúrate de que este proceso no elimine datos importantes
cat <<EOL >archivo.json
{
    "TOKEN": "$TOKEN",
    "NGROK_TOKEN": "$NGROK_TOKEN"
    // Continuar con todas las demás credenciales
}
EOL

# Iniciar el bot en segundo plano con tmux
tmux new-session -d -s bot_session '/usr/local/bin/python3.11 CCLD.py'

echo "Bot instalado y configurado correctamente."
