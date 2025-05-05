#!/bin/bash
set -eux

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends openssh-server rkhunter net-tools

id -u sftpuser >/dev/null 2>&1 || useradd -m -s /usr/sbin/nologin sftpuser
mkdir -p /home/sftpuser/upload
chown root:root /home/sftpuser && chmod 755 /home/sftpuser
chown sftpuser:sftpuser /home/sftpuser/upload

grep -qxF 'Match User sftpuser' /etc/ssh/sshd_config || cat <<EOF >> /etc/ssh/sshd_config
Match User sftpuser
    ChrootDirectory /home/sftpuser
    ForceCommand internal-sftp
    AllowTCPForwarding no
    X11Forwarding no
EOF

systemctl restart ssh

SSH_DIR="/home/sftpuser/.ssh"
mkdir -p "$SSH_DIR"
chown sftpuser:sftpuser "$SSH_DIR"
chmod 700 "$SSH_DIR"

KEY_PRIV="/vagrant/keys/$(hostname)"
KEY_PUB="${KEY_PRIV}.pub"

if [ -r "$KEY_PRIV" ] && [ -r "$KEY_PUB" ]; then
  cp "$KEY_PRIV" "$SSH_DIR/id_ed25519"
  cp "$KEY_PUB" "$SSH_DIR/id_ed25519.pub"
else
  sudo -u sftpuser ssh-keygen -t ed25519 -f "$SSH_DIR/id_ed25519" -N '' -C "$(hostname)@vagrant"
fi

chown sftpuser:sftpuser "$SSH_DIR/id_ed25519" "$SSH_DIR/id_ed25519.pub"
chmod 600 "$SSH_DIR/id_ed25519"

:> "$SSH_DIR/authorized_keys"
for pub in /vagrant/keys/sftp1.pub /vagrant/keys/sftp2.pub /vagrant/keys/sftp3.pub; do
  [ -f "$pub" ] && cat "$pub" >> "$SSH_DIR/authorized_keys"
done

chown sftpuser:sftpuser "$SSH_DIR/authorized_keys"
chmod 600 "$SSH_DIR/authorized_keys"
