#!/bin/bash

# Create log file
LOG_FILE="/home/ubuntu/setup.log"
touch $LOG_FILE
chown ubuntu:ubuntu $LOG_FILE

# Function for logging
log() {
    echo "$(date +"%Y-%m-%d %H:%M:%S") - $1" | tee -a $LOG_FILE
}

log "Beginning Serka setup..."

# install and configure nginx
log "Installing nginx..."
apt-get install -y nginx >> $LOG_FILE 2>&1
cat > /etc/nginx/sites-available/default <<EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
log "Restarting nginx..."
systemctl restart nginx >> $LOG_FILE 2>&1

# install podman
log "Updating package lists..."
apt-get update -y >> $LOG_FILE 2>&1
log "Installing podman..."
apt-get install -y podman >> $LOG_FILE 2>&1
log "Installing podman-compose..."
apt-get install -y podman-compose >> $LOG_FILE 2>&1
echo 'unqualified-search-registries = ["docker.io"]' | sudo tee -a /etc/containers/registries.conf >> $LOG_FILE 2>&1

# setup local repo to import data using utility scripts
log "Switching to ubuntu user"
su - ubuntu << 'EOF_UBUNTU'
#start server
LOG_FILE="/home/ubuntu/setup.log"

git config --global http.sslVerify false >> $LOG_FILE 2>&1

git clone https://github.com/ukceh-rse/serka.git /home/ubuntu/serka >> $LOG_FILE 2>&1

cd /home/ubuntu/serka

# Generate random password for neo4j (username must be default "neo4j")
RANDOM_PASSWORD="$(head /dev/urandom | tr -dc 'a-z0-9' | head -c 8)"

touch .env
cat > .env << ENV_CONTENT
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=$RANDOM_PASSWORD
NEO4J_URI=bolt://neo4j-container:7687
AWS_DEFAULT_REGION=eu-west-2
ENV_CONTENT

git checkout geocoding >> $LOG_FILE 2>&1
EOF_UBUNTU

cd /home/ubuntu/serka
podman-compose -f container-compose[aws].yml up -d >> $LOG_FILE 2>&1

# Setup uv locally to run the data import script.
# Note this is just for testing, data should be imported and processed sperately and then made accessible to the instance.
sudo snap install astral-uv --classic >> $LOG_FILE 2>&1
uv sync >> $LOG_FILE 2>&1

# Note this will only import a small number of datasets for testing
uv run scripts/ingest-data.py >> $LOG_FILE 2>&1

log "Serka setup completed"
