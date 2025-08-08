#!/bin/bash

# Create log file
LOG_FILE="/home/ubuntu/initialize.log"
touch $LOG_FILE
chown ubuntu:ubuntu $LOG_FILE

# Function for logging
log() {
    echo "$(date +"%Y-%m-%d %H:%M:%S") - $1" | tee -a $LOG_FILE
}

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

log "Switching to ubuntu user"
su - ubuntu << 'EOF_UBUNTU'
#start server
LOG_FILE="/home/ubuntu/initialize.log"

git config --global http.sslVerify false >> $LOG_FILE 2>&1

git clone https://github.com/ukceh-rse/serka.git /home/ubuntu/serka >> $LOG_FILE 2>&1

cd /home/ubuntu/serka

touch .env

git checkout bedrock-integration >> $LOG_FILE 2>&1

podman-compose -f podman-compose[aws].yml up -d >> $LOG_FILE 2>&1
EOF_UBUNTU

log "Initialization completed"
