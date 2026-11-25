#!/bin/bash
# EC2 user data (a Terraform template), run once on first boot: installs Docker, downloads the
# Redis snapshot, clones Serka and starts it.
set -euo pipefail
exec > >(tee -a /var/log/serka-setup.log) 2>&1

# compose.yaml mounts $${HOME}/.aws; cloud-init may not set HOME
export HOME=/root

# Redis forks for background saves; without overcommit a fork can fail under memory pressure
sysctl -w vm.overcommit_memory=1
echo "vm.overcommit_memory = 1" > /etc/sysctl.d/99-redis.conf

apt-get update -y
apt-get install -y docker.io docker-compose-v2 git
snap install aws-cli --classic
systemctl enable --now docker

# Redis loads dump.rdb from its data directory on startup
mkdir -p /opt/serka-data/redis
aws s3 cp "${redis_dump}" /opt/serka-data/redis/dump.rdb

git clone https://github.com/ukceh-rse/serka.git /opt/serka
cd /opt/serka
git checkout "${git_ref}"
cp .env.example .env
echo "REDIS_DATA_DIR=/opt/serka-data/redis" >> .env

docker compose up -d --build
