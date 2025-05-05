require 'fileutils'

# Host-side keys directory (must exist in project root)
KEYS_DIR = File.expand_path('keys', __dir__)
FileUtils.mkdir_p(KEYS_DIR)
FileUtils.chmod 0o700, KEYS_DIR

# Check for ssh-keygen availability
def ssh_keygen_available?
  system('ssh-keygen -V', out: File::NULL, err: File::NULL)
end

# Generate host-side keypairs if ssh-keygen is present
if ssh_keygen_available?
  (1..3).each do |i|
    name = "sftp#{i}"
    priv = File.join(KEYS_DIR, name)
    pub  = "#{priv}.pub"
    unless File.exist?(priv) && File.exist?(pub)
      if system('ssh-keygen', '-t', 'ed25519', '-f', priv, '-N ''', '-C', "#{name}@vagrant")
        FileUtils.chmod 0o600, priv, pub
      else
        warn "[vagrant] Warning: ssh-keygen failed for #{name}; you may need to generate keys manually."
      end
    end
  end
else
  warn "[vagrant] ssh-keygen not found on host; VM will generate keys internally."
end

Vagrant.configure('2') do |config|
  config.vm.box = 'ubuntu/jammy64'
  config.vm.boot_timeout = 300

  # Mount host keys read-only
  config.vm.synced_folder KEYS_DIR, '/vagrant/keys', owner: 'root', group: 'root', mount_options: ['ro', 'dmode=700', 'fmode=600']

  # Global SSH hardening
  config.vm.provision 'shell', inline: <<-SHELL
    set -eux
    grep -qxF 'PasswordAuthentication no' /etc/ssh/sshd_config || sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
    grep -qxF 'PubkeyAuthentication yes' /etc/ssh/sshd_config || sed -i 's/^#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config
    grep -qxF 'PermitRootLogin no'    /etc/ssh/sshd_config || echo 'PermitRootLogin no' >> /etc/ssh/sshd_config
    systemctl restart ssh
  SHELL

  # Define three SFTP nodes
  (1..3).each do |i|
    config.vm.define "sftp#{i}" do |vm|
      vm.vm.provider 'virtualbox' do |vb|
        vb.gui = true
        vb.memory = 5120
        vb.cpus   = 4
        vb.customize ['modifyvm', :id, '--uartmode1', 'disconnected']
        vb.customize ['modifyvm', :id, '--uartmode2', 'disconnected']
      end

      vm.vm.hostname = "sftp#{i}"
      vm.vm.network  'private_network', ip: "192.168.56.10#{i}"
      vm.vm.network  'forwarded_port', guest: 22, host: 2200 + i

      # Base provisioning
      vm.vm.provision 'shell', inline: <<-SHELL
        set -eux
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -y
        apt-get install -y --no-install-recommends openssh-server rkhunter net-tools

        # SFTP chroot user
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

        # SSH key setup for sftpuser
        SSH_DIR="/home/sftpuser/.ssh"
        mkdir -p "$SSH_DIR"
        chown sftpuser:sftpuser "$SSH_DIR"
        chmod 700 "$SSH_DIR"

        # Copy or generate host keypair for ring transfer
        KEY_PRIV="/vagrant/keys/sftp#{i}"
        KEY_PUB="/vagrant/keys/sftp#{i}.pub"
        if [ -r "$KEY_PRIV" ] && [ -r "$KEY_PUB" ]; then
          cp "$KEY_PRIV" "$SSH_DIR/id_ed25519"
          cp "$KEY_PUB" "$SSH_DIR/id_ed25519.pub"
        else
          sudo -u sftpuser ssh-keygen -t ed25519 -f "$SSH_DIR/id_ed25519" -N '' -C "sftp#{i}@vagrant"
        fi
        chown sftpuser:sftpuser "$SSH_DIR/id_ed25519" "$SSH_DIR/id_ed25519.pub"
        chmod 600        "$SSH_DIR/id_ed25519"

        # Build authorized_keys for ring of SFTP nodes
        :> "$SSH_DIR/authorized_keys"
        for pub in /vagrant/keys/sftp1.pub /vagrant/keys/sftp2.pub /vagrant/keys/sftp3.pub; do
          [ -f "$pub" ] && cat "$pub" >> "$SSH_DIR/authorized_keys"
        done
        chown sftpuser:sftpuser "$SSH_DIR/authorized_keys"
        chmod 600            "$SSH_DIR/authorized_keys"
      SHELL

      # Copy and schedule generate.sh under sftpuser
      vm.vm.provision 'file', source: 'scripts/generate.sh', destination: '/tmp/generate.sh'
      vm.vm.provision 'shell', inline: <<-SHELL
        mv /tmp/generate.sh /home/sftpuser/generate.sh
        chmod 750 /home/sftpuser/generate.sh
        chown sftpuser:sftpuser /home/sftpuser/generate.sh
        (crontab -u sftpuser -l 2>/dev/null; echo "*/5 * * * * /home/sftpuser/generate.sh") | crontab -u sftpuser -
      SHELL
    end
  end
end