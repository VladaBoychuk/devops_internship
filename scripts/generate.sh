#!/usr/bin/env bash
set -euo pipefail

# Скрипт generate.sh запускається кожні 5 хв для створення та передачі файлів між SFTP-вузлами

HOST="$(hostname)"
TS="$(date +'%Y%m%d_%H%M%S')"
FILENAME="${HOST}_${TS}.txt"
LOCAL_PATH="/home/sftpuser/${FILENAME}"

# Записати дату, час та ім'я вузла у файл
echo "${TS} ${HOST}" > "${LOCAL_PATH}"

# Визначення IP наступного вузла в кільцевому ланцюжку
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

# Виконати SFTP передачу у фоновому режимі
sftp -oBatchMode=yes -i /home/sftpuser/.ssh/id_ed25519 \
     sftpuser@${NEXT_IP} <<EOF
put "${LOCAL_PATH}" /home/sftpuser/upload/${FILENAME}
bye
EOF

# Видалити локальний файл після успішної передачі
rm -f "${LOCAL_PATH}"
