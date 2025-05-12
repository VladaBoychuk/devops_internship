#!/bin/bash
set -eux

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends openssh-server rkhunter net-tools coreutils wget curl sshpass

# teamporaly enable password authentication in SSH
sed -i 's/#PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config

systemctl restart ssh

echo "Setting up user sftpuser and directories for $(hostname)..."
sudo useradd -m -d /home/sftpuser -s /bin/bash sftpuser

echo "sftpuser:$SFTP_PASSWORD" | sudo chpasswd

UPLOAD_DIR="/home/sftpuser/upload"
mkdir -p "${UPLOAD_DIR}"

CRON_LOGS_DIR="/home/sftpuser/cron_logs"
mkdir -p "${CRON_LOGS_DIR}"

chown sftpuser:sftpuser /home/sftpuser
chmod 755 /home/sftpuser

chown sftpuser:sftpuser "${UPLOAD_DIR}"
chmod 750 "${UPLOAD_DIR}"

chown sftpuser:sftpuser "${CRON_LOGS_DIR}"
chmod 750 "${CRON_LOGS_DIR}"
echo "User sftpuser and directories (upload, cron_logs) set up."

sed -i 's/PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config.d/60-cloudimg-settings.conf
