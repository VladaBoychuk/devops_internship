#!/bin/bash
set -euo pipefail

_date="/usr/bin/date"
_hostname="/usr/bin/hostname"
_sftp="/usr/bin/sftp"
_rm="/usr/bin/rm"
_tail="/usr/bin/tail"

CRON_FILES_DIR="/home/sftpuser/cron_logs"

if [ ! -d "${CRON_FILES_DIR}" ]; then
    if command -v logger > /dev/null; then
        logger -t generate.sh "Error: Log directory ${CRON_FILES_DIR} does not exist for sftpuser on $(hostname)."
    fi
    exit 1
fi

HOST="$($_hostname)"
TS_FILE=$($_date +'%Y%m%d_%H%M%S')
TS_LOG=$($_date +'%Y-%m-%d %H:%M:%S')

FILENAME="${HOST}_${TS_FILE}.txt"
LOCAL_PATH="${CRON_FILES_DIR}/${FILENAME}"
REMOTE_UPLOAD_PATH_INSIDE_CHROOT="/upload" 
LOG_FILE="${CRON_FILES_DIR}/generate.log" 
ERROR_LOG_FILE="${CRON_FILES_DIR}/generate_error.log"

TARGET_IPS=()
case "${HOST}" in
  sftp1)
    TARGET_IPS=("192.168.56.102" "192.168.56.103")
    ;;
  sftp2)
    TARGET_IPS=("192.168.56.101" "192.168.56.103")
    ;;
  sftp3)
    TARGET_IPS=("192.168.56.101" "192.168.56.102")
    ;;
  *)
    echo "${TS_LOG} Error: Unknown or empty host: [${HOST}] on $(hostname)" >> "${ERROR_LOG_FILE}"
    $_rm -f "${CRON_FILES_DIR}/${FILENAME}" 2>/dev/null
    exit 1
    ;;
esac

if [ ${#TARGET_IPS[@]} -eq 0 ]; then
  echo "${TS_LOG} No target IPs defined for host ${HOST}. Exiting." >> "${LOG_FILE}"
  exit 0
fi

echo "${TS_LOG} Source: ${HOST}" > "${LOCAL_PATH}"
echo "${TS_LOG} Host: ${HOST}. Generated file ${FILENAME}. Will attempt SFTP to: ${TARGET_IPS[*]}" >> "${LOG_FILE}"

OVERALL_SFTP_SUCCESS=true

for NEXT_IP in "${TARGET_IPS[@]}"; do
  echo "${TS_LOG} Attempting SFTP from ${HOST} to ${NEXT_IP} for file ${FILENAME}" >> "${LOG_FILE}"

  $_sftp -oBatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
       -i /home/sftpuser/.ssh/id_ed25519 \
       sftpuser@${NEXT_IP} 2>> "${ERROR_LOG_FILE}" <<EOF
cd ${REMOTE_UPLOAD_PATH_INSIDE_CHROOT}
put "${LOCAL_PATH}" "${FILENAME}"
ls -l "${FILENAME}"
bye
EOF

  SFTP_EXIT_CODE=$?
  if [ $SFTP_EXIT_CODE -ne 0 ]; then
      echo "${TS_LOG} Error: SFTP command from ${HOST} to ${NEXT_IP} failed with exit code ${SFTP_EXIT_CODE}. Check ${ERROR_LOG_FILE}" >> "${ERROR_LOG_FILE}"
      echo "${TS_LOG} SFTP to ${NEXT_IP} FAILED (exit code ${SFTP_EXIT_CODE}). See ${ERROR_LOG_FILE}." >> "${LOG_FILE}"
      OVERALL_SFTP_SUCCESS=false
  else
      echo "${TS_LOG} Success: SFTP from ${HOST} to ${NEXT_IP} completed for file ${FILENAME}." >> "${LOG_FILE}"
  fi
done

$_rm -f "${LOCAL_PATH}"

if $OVERALL_SFTP_SUCCESS; then
  echo "${TS_LOG} All SFTP operations for ${FILENAME} completed successfully." >> "${LOG_FILE}"
  exit 0
else
  echo "${TS_LOG} One or more SFTP operations for ${FILENAME} failed." >> "${LOG_FILE}"
  exit 1
fi