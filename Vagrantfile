Vagrant.configure("2") do |config|
  # Base box and extended boot timeout
  config.vm.box = "ubuntu/jammy64"
  config.vm.boot_timeout = 300

  # Global SSH hardening
  config.vm.provision "shell", inline: <<-SHELL
    # disable login by password
    sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
    # enable only public keys
    sed -i 's/^#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config
    # protect the root login
    echo "PermitRootLogin no" >> /etc/ssh/sshd_config
    systemctl restart ssh
  SHELL

  # Define three SFTP nodes
  (1..3).each do |i|
    config.vm.define "sftp#{i}" do |vm|
      vm.vm.provider "virtualbox" do |vb|
        # open a VM window (for debugging)
        vb.gui = true
        # disable the virtual UART ports (disconnected) to avoid errors on Windows
        vb.customize ["modifyvm", :id, "--uartmode1", "disconnected"]
        vb.customize ["modifyvm", :id, "--uartmode2", "disconnected"]
      end

      vm.vm.hostname = "sftp#{i}"
      vm.vm.network "private_network", ip: "192.168.56.10#{i}"
      vm.vm.network "forwarded_port", guest: 22, host: 2200 + i

      # Per-VM provisioning
      vm.vm.provision "shell", inline: <<-SHELL
        # disables apt's interactive mode so that packages are installed without interruption
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -y
        apt-get install -y --no-install-recommends openssh-server rkhunter net-tools

        # create a non-login SFTP user
        useradd -m -s /usr/sbin/nologin sftpuser

        # set up chroot and upload directory
        mkdir -p /home/sftpuser/upload
        chown root:root /home/sftpuser
        chmod 755 /home/sftpuser
        chown sftpuser:sftpuser /home/sftpuser/upload

        # append SFTP-only configuration to sshd
        cat <<EOF >> /etc/ssh/sshd_config
Match User sftpuser
    ChrootDirectory /home/sftpuser
    ForceCommand internal-sftp
    AllowTCPForwarding no
    X11Forwarding no
EOF
        systemctl restart ssh

        # install the public key for sftpuser
        mkdir -p /home/sftpuser/.ssh
        cat /vagrant/id_ed25519.pub >> /home/sftpuser/.ssh/authorized_keys
        chown -R sftpuser:sftpuser /home/sftpuser/.ssh
        chmod 700 /home/sftpuser/.ssh
        chmod 600 /home/sftpuser/.ssh/authorized_keys
      SHELL
    end
  end
end
