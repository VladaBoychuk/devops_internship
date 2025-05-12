#!/bin/bash
set -eux

export DEBIAN_FRONTEND=noninteractive

SSHD_CONFIG="/etc/ssh/sshd_config"
echo "Starting SSHD configuration for $(hostname)..."

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
        echo "Error: sftp-server binary not found on $(hostname)! Cannot configure SFTP subsystem." >&2
        exit 1
    fi
fi
echo "Using sftp-server path: $SFTP_SERVER_PATH on $(hostname)"
SFTP_CONFIG_LINE="Subsystem sftp $SFTP_SERVER_PATH"

if grep -q "^[[:space:]]*Subsystem[[:space:]]\+sftp" "$SSHD_CONFIG"; then
    sudo sed -i -e '/^[[:space:]]*Subsystem[[:space:]]\+sftp/d' "$SSHD_CONFIG"
fi
if [ -s "$SSHD_CONFIG" ] && [ "$(tail -c1 "$SSHD_CONFIG" | wc -l)" -eq 0 ]; then
    echo | sudo tee -a "$SSHD_CONFIG" > /dev/null
fi
echo "$SFTP_CONFIG_LINE" | sudo tee -a "$SSHD_CONFIG" > /dev/null

MATCH_USER_START_LINE="Match User sftpuser"
sudo sed -i -e "/^${MATCH_USER_START_LINE}$/d" \
           -e "/^[[:space:]]*ChrootDirectory \/home\/sftpuser$/d" \
           -e "/^[[:space:]]*ForceCommand internal-sftp$/d" \
           -e "/^[[:space:]]*AllowTCPForwarding no$/d" \
           -e "/^[[:space:]]*X11Forwarding no$/d" \
           "$SSHD_CONFIG"

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

echo "Validating SSHD configuration on $(hostname)..."
sudo sshd -t
if [ $? -eq 0 ]; then
  echo "SSHD configuration is valid. Restarting sshd on $(hostname)..."
  sudo systemctl restart sshd
  echo "sshd restarted on $(hostname)."
else
  echo "Error: sshd_config test failed on $(hostname)! Please check $SSHD_CONFIG on the VM." >&2
  sudo cat "$SSHD_CONFIG"
  exit 1
fi
echo "SSHD configuration finished for $(hostname)."

echo "Setting up SSH keys for sftpuser on $(hostname)..."
CURRENT_HOSTNAME=$(hostname)


echo "Setting up RKHunter and performing initial check on $(hostname)..."
RKHUNTER_CONF="/etc/rkhunter.conf"

if [ -x "/usr/bin/wget" ]; then
    sudo sed -i -e 's|^[#[:space:]]*WEB_CMD=.*wget.*|WEB_CMD="/usr/bin/wget -q -O -"|' \
               -e 's|^WEB_CMD="/bin/false"|#WEB_CMD="/bin/false"|' \
               -e '/^WEB_CMD="\/usr\/bin\/curl -Ls"$/s/^WEB_CMD/#WEB_CMD/' \
               -e '/^WEB_CMD="\/usr\/bin\/lynx -dump"$/s/^WEB_CMD/#WEB_CMD/' \
               "${RKHUNTER_CONF}"
    if ! grep -q '^WEB_CMD="/usr/bin/wget -q -O -"' "${RKHUNTER_CONF}"; then
        sudo sed -i -e '/^WEB_CMD=/d' "${RKHUNTER_CONF}"
        echo 'WEB_CMD="/usr/bin/wget -q -O -"' | sudo tee -a "${RKHUNTER_CONF}" > /dev/null
    fi
elif [ -x "/usr/bin/curl" ]; then
    sudo sed -i -e 's|^[#[:space:]]*WEB_CMD=.*curl.*|WEB_CMD="/usr/bin/curl -Ls"|' \
               -e 's|^WEB_CMD="/bin/false"|#WEB_CMD="/bin/false"|' \
               -e '/^WEB_CMD="\/usr\/bin\/wget -q -O -"$/s/^WEB_CMD/#WEB_CMD/' \
               -e '/^WEB_CMD="\/usr\/bin\/lynx -dump"$/s/^WEB_CMD/#WEB_CMD/' \
               "${RKHUNTER_CONF}"
    if ! grep -q '^WEB_CMD="/usr/bin/curl -Ls"' "${RKHUNTER_CONF}"; then
        sudo sed -i -e '/^WEB_CMD=/d' "${RKHUNTER_CONF}"
        echo 'WEB_CMD="/usr/bin/curl -Ls"' | sudo tee -a "${RKHUNTER_CONF}" > /dev/null
    fi
else
    echo "Warning: Neither wget nor curl found on $(hostname). RKHunter updates may fail." >&2
fi

echo "Updating RKHunter data files on $(hostname)..."
if ! timeout 600 sudo rkhunter --update --nocolors; then
    echo "Warning: rkhunter --update failed or timed out on $(hostname)." >&2
fi

echo "Updating RKHunter file properties database on $(hostname)..."
if ! timeout 300 sudo rkhunter --propupd --nocolors; then
    echo "Warning: rkhunter --propupd failed or timed out on $(hostname)." >&2
fi
