#!/bin/bash

if [ ! -f /home/sftpuser/.ssh/id_ed25519 ]; then
    sudo -u sftpuser ssh-keygen -t ed25519 -N "" -f /home/sftpuser/.ssh/id_ed25519
    echo "SSH key generated for sftpuser."
else
    echo "SSH key already exists for sftpuser."
fi

sudo chmod 700 /home/sftpuser/.ssh
sudo chmod 600 /home/sftpuser/.ssh/id_ed25519
sudo chmod 644 /home/sftpuser/.ssh/id_ed25519.pub
sudo chown -R sftpuser:sftpuser /home/sftpuser

sed -i 's/PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config.d/60-cloudimg-settings.conf
systemctl restart ssh
echo "SSH key generation and permission setting complete for sftpuser."