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
      if system('ssh-keygen', '-t', 'ed25519', '-f', priv, '-N', '', '-C', "#{name}@vagrant")
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

  # Global SSH hardening (safe and idempotent)
  config.vm.provision 'shell', inline: <<-SHELL
    set -eux
    grep -qxF 'PasswordAuthentication no' /etc/ssh/sshd_config || sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
    grep -qxF 'PubkeyAuthentication yes' /etc/ssh/sshd_config || sed -i 's/^#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config
    grep -qxF 'PermitRootLogin no'    /etc/ssh/sshd_config || echo 'PermitRootLogin no' >> /etc/ssh/sshd_config
    systemctl restart ssh
  SHELL

  (1..3).each do |i|
    config.vm.define "sftp#{i}" do |vm|
      vm.vm.provider 'virtualbox' do |vb|
        vb.gui = true
        vb.customize ['modifyvm', :id, '--uartmode1', 'disconnected']
        vb.customize ['modifyvm', :id, '--uartmode2', 'disconnected']
      end

      vm.vm.hostname = "sftp#{i}"
      vm.vm.network  'private_network', ip: "192.168.56.10#{i}"
      vm.vm.network  'forwarded_port', guest: 22, host: 2200 + i

      vm.vm.provision 'shell', inline: <<-SHELL
        set -eux
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -y
        apt-get install -y --no-install-recommends openssh-server rkhunter net-tools

        # SFTP user (chroot-only)
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

        # M2M user setup
        id -u m2m >/dev/null 2>&1 || useradd -m -s /bin/bash m2m
        mkdir -p /home/m2m/.ssh && chown m2m:m2m /home/m2m/.ssh && chmod 700 /home/m2m/.ssh

        # SSH key management
        if [ -r /vagrant/keys/sftp#{i} ]; then
          cp /vagrant/keys/sftp#{i} /home/m2m/.ssh/id_ed25519
        else
          sudo -u m2m ssh-keygen -t ed25519 -f /home/m2m/.ssh/id_ed25519 -N '' -C "sftp#{i}@vagrant"
        fi
        chown m2m:m2m /home/m2m/.ssh/id_ed25519 && chmod 600 /home/m2m/.ssh/id_ed25519

        # Build authorized_keys from static pub files
        > /home/m2m/.ssh/authorized_keys
        for keyfile in /vagrant/keys/sftp1.pub /vagrant/keys/sftp2.pub /vagrant/keys/sftp3.pub; do
          [ -f "$keyfile" ] && cat "$keyfile" >> /home/m2m/.ssh/authorized_keys
        done
        chown m2m:m2m /home/m2m/.ssh/authorized_keys && chmod 600 /home/m2m/.ssh/authorized_keys

        # Remove host-side private copy
        rm -f /vagrant/keys/sftp#{i}
      SHELL
    end
  end
end
