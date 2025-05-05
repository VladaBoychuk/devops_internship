#!/bin/bash
set -eux

grep -qxF 'PasswordAuthentication no' /etc/ssh/sshd_config || sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
grep -qxF 'PubkeyAuthentication yes' /etc/ssh/sshd_config || sed -i 's/^#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config
grep -qxF 'PermitRootLogin no' /etc/ssh/sshd_config || echo 'PermitRootLogin no' >> /etc/ssh/sshd_config

systemctl restart ssh
