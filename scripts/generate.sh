#!/usr/bin/env bash
set -euo pipefail


HOST="$(hostname)"
TS="$(date +'%Y%m%d_%H%M%S')"
FILENAME="${HOST}_${TS}.txt"
LOCAL_PATH="/home/sftpuser/${FILENAME}"

# Записати дату, час та ім'я вузла у файл
echo "${TS} ${HOST}" > "${LOCAL_PATH}"

case "${HOST}" in
  sftp1)
    NEXT_IP="192.168.56.102" ;;  # IP sftp2
  sftp2)
    NEXT_IP="192.168.56.103" ;;  # IP sftp3
  sftp3)
    NEXT_IP="192.168.56.101" ;;  # IP sftp1
  *)
    echo "Unknown host: ${HOST}" >&2
    exit 1
    ;;
esac

sftp -oBatchMode=yes -i /home/sftpuser/.ssh/id_ed25519 \
     sftpuser@${NEXT_IP} <<EOF
put "${LOCAL_PATH}" /home/sftpuser/upload/${FILENAME}
bye
EOF

rm -f "${LOCAL_PATH}"
