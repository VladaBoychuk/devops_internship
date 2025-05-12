vms=("$SFTP_IP_1" "$SFTP_IP_2" "$SFTP_IP_3")

copy_ssh_key() {
    local host=$1
    sudo -u sftpuser ssh-keyscan -H $host >> /home/sftpuser/.ssh/known_hosts
    sshpass -p "verystrongpassword1" ssh-copy-id -o StrictHostKeyChecking=no -i /home/sftpuser/.ssh/id_ed25519.pub sftpuser@$host
}

# Ensure sshpass is installed
sudo apt-get install -y sshpass

for vm in "${vms[@]}"; do
    if [[ $vm != $(hostname -I | awk '{print $2}') ]]; then
        echo "Copying SSH key to $vm"
        copy_ssh_key $vm
    fi
done

echo "SSH key exchange complete."