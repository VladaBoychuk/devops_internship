echo "Provisioning generate.sh and cron job for sftpuser on $(hostname)..."
if [ -d "/home/sftpuser" ]; then
    mv /tmp/generate.sh /home/sftpuser/generate.sh

    chown root:root /home/sftpuser
    chmod 755 /home/sftpuser

    chmod 750 /home/sftpuser/generate.sh
    chown sftpuser:sftpuser /home/sftpuser/generate.sh
    
    
    echo "generate.sh moved and permissions set for $(hostname)."

    (crontab -u sftpuser -l 2>/dev/null | grep -v -F "/home/sftpuser/generate.sh" ; echo "*/5 * * * * /home/sftpuser/generate.sh") | crontab -u sftpuser -
    echo "Cron job for generate.sh configured for sftpuser on $(hostname)."
else
    echo "Error: /home/sftpuser does not exist. Cannot setup generate.sh on $(hostname)." >&2
    exit 1
fi