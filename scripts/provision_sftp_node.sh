#!/bin/bash
set -eux

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends openssh-server rkhunter net-tools coreutils

# --- User and Directory Setup ---
echo "Setting up user sftpuser and directories..."
id -u sftpuser >/dev/null 2>&1 || useradd -m -s /usr/sbin/nologin sftpuser

# SFTP Upload directory
UPLOAD_DIR="/home/sftpuser/upload"
mkdir -p "${UPLOAD_DIR}"

# Cron logs directory for sftpuser's scripts
CRON_LOGS_DIR="/home/sftpuser/cron_logs"
mkdir -p "${CRON_LOGS_DIR}"

# Set ownership for chroot: /home/sftpuser must be owned by root
chown root:root /home/sftpuser
chmod 755 /home/sftpuser

# Set ownership for subdirectories where sftpuser needs to write
chown sftpuser:sftpuser "${UPLOAD_DIR}"
chmod 750 "${UPLOAD_DIR}" # Owner can rwx, group can rx

chown sftpuser:sftpuser "${CRON_LOGS_DIR}"
chmod 750 "${CRON_LOGS_DIR}" # Owner can rwx, group can rx
echo "User sftpuser and directories (upload, cron_logs) set up."

# --- SSHD Configuration ---
SSHD_CONFIG="/etc/ssh/sshd_config"
echo "Starting SSHD configuration..."

# 1. Ensure Subsystem sftp is present and correct at the global level
SFTP_SERVER_PATH=""
if [ -x "/usr/lib/openssh/sftp-server" ]; then
    SFTP_SERVER_PATH="/usr/lib/openssh/sftp-server"
elif [ -x "/usr/libexec/openssh/sftp-server" ]; then
    SFTP_SERVER_PATH="/usr/libexec/openssh/sftp-server"
else
    FOUND_PATH=$(whereis -b sftp-server | awk '{print $2}')
    if [ -z "$FOUND_PATH" ] || [ ! -x "$FOUND_PATH" ]; then
         FOUND_PATH=$(which sftp-server 2>/dev/null)
    fi
    if [ -n "$FOUND_PATH" ] && [ -x "$FOUND_PATH" ]; then
        SFTP_SERVER_PATH="$FOUND_PATH"
    else
        echo "Error: sftp-server binary not found!" >&2
        exit 1
    fi
fi
echo "Using sftp-server path: $SFTP_SERVER_PATH"
SFTP_CONFIG_LINE="Subsystem sftp $SFTP_SERVER_PATH"

if ! grep -qFx "$SFTP_CONFIG_LINE" "$SSHD_CONFIG"; then
    echo "Configuring SFTP Subsystem..."
    sudo sed -i -e '/^[[:space:]]*Subsystem[[:space:]]\+sftp/d' "$SSHD_CONFIG"
    if [ -s "$SSHD_CONFIG" ] && [ "$(tail -c1 "$SSHD_CONFIG" | wc -l)" -eq 0 ]; then
        echo | sudo tee -a "$SSHD_CONFIG" > /dev/null
    fi
    echo "$SFTP_CONFIG_LINE" | sudo tee -a "$SSHD_CONFIG" > /dev/null
    echo "SFTP Subsystem line configured: $SFTP_CONFIG_LINE"
else
    echo "Correct SFTP Subsystem line already exists."
fi

# 2. Ensure Match User sftpuser block is present
MATCH_USER_START_LINE="Match User sftpuser"
if ! grep -qF "$MATCH_USER_START_LINE" "$SSHD_CONFIG"; then
    echo "Adding Match User sftpuser block..."
    if [ -s "$SSHD_CONFIG" ] && [ "$(tail -c1 "$SSHD_CONFIG" | wc -l)" -eq 0 ]; then
        echo | sudo tee -a "$SSHD_CONFIG" > /dev/null
    fi
    cat <<EOF | sudo tee -a "$SSHD_CONFIG" > /dev/null
Match User sftpuser
    ChrootDirectory /home/sftpuser
    ForceCommand internal-sftp
    AllowTCPForwarding no
    X11Forwarding no
EOF
    echo "Match User sftpuser block added."
else
    echo "Match User sftpuser block already exists or similar line found."
fi

# 3. Validate and Restart SSH
echo "Validating SSHD configuration..."
sudo sshd -t
if [ $? -eq 0 ]; then
  echo "SSHD configuration is valid. Restarting sshd..."
  sudo systemctl restart sshd
  echo "sshd restarted."
else
  echo "Error: sshd_config test failed! Please check $SSHD_CONFIG on the VM." >&2
  echo "--- Dumping $SSHD_CONFIG ---"
  sudo cat "$SSHD_CONFIG"
  echo "--- End of $SSHD_CONFIG dump ---"
  exit 1
fi
echo "SSHD configuration finished."

# --- SSH Key Setup for sftpuser ---
echo "Setting up SSH keys for sftpuser..."
SSH_DIR="/home/sftpuser/.ssh" # This directory will be owned by sftpuser
mkdir -p "$SSH_DIR"
chown sftpuser:sftpuser "$SSH_DIR"
chmod 700 "$SSH_DIR"

KEY_PRIV_SOURCE="/vagrant/keys/$(hostname)"
KEY_PUB_SOURCE="${KEY_PRIV_SOURCE}.pub"
KEY_PRIV_DEST="$SSH_DIR/id_ed25519"
KEY_PUB_DEST="$SSH_DIR/id_ed25519.pub"

if [ -r "$KEY_PRIV_SOURCE" ] && [ -r "$KEY_PUB_SOURCE" ]; then
  cp "$KEY_PRIV_SOURCE" "$KEY_PRIV_DEST"
  cp "$KEY_PUB_SOURCE" "$KEY_PUB_DEST"
  echo "Copied keys from /vagrant/keys to $SSH_DIR"
else
  if [ ! -f "$KEY_PRIV_DEST" ]; then
      echo "Keys not found in /vagrant/keys, generating new ones in $SSH_DIR..."
      sudo -u sftpuser ssh-keygen -t ed25519 -f "$KEY_PRIV_DEST" -N '' -C "$(hostname)@vagrant"
  else
      echo "Keys already exist in $SSH_DIR, skipping generation/copy."
  fi
fi

chown sftpuser:sftpuser "$KEY_PRIV_DEST" "$KEY_PUB_DEST"
chmod 600 "$KEY_PRIV_DEST"
chmod 644 "$KEY_PUB_DEST"

AUTHORIZED_KEYS_FILE="$SSH_DIR/authorized_keys"
sudo -u sftpuser touch "$AUTHORIZED_KEYS_FILE"
echo "Setting up authorized_keys in $AUTHORIZED_KEYS_FILE..."
if [ -d "/vagrant/keys" ] && [ -n "$(ls -A /vagrant/keys/sftp*.pub 2>/dev/null)" ]; then
    cat /vagrant/keys/sftp*.pub > "$AUTHORIZED_KEYS_FILE"
    echo "Populated authorized_keys from /vagrant/keys."
else
    echo "Warning: No public keys found in /vagrant/keys/sftp*.pub to populate authorized_keys."
fi
chown sftpuser:sftpuser "$AUTHORIZED_KEYS_FILE"
chmod 600 "$AUTHORIZED_KEYS_FILE"

echo "SSH keys setup for sftpuser finished."
echo "SFTP node provisioning finished for $(hostname)."