#!/bin/bash

# install and configure nginx
apt-get install -y nginx
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
systemctl restart nginx

# install podman
apt-get update -y
apt-get install -y podman
apt-get install -y podman-compose
echo "Podman and Podman-Compose installed successfully" > /home/ubuntu/installation_complete.txt

#start server
podman run -dt -p 8080:80/tcp docker.io/library/httpd
