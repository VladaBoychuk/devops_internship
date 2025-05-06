require 'fileutils'

# Host-side keys directory (must exist in project root)
KEYS_DIR = File.expand_path('keys', __dir__)
FileUtils.mkdir_p(KEYS_DIR)
FileUtils.chmod 0o700, KEYS_DIR

(1..3).each do |i|
  name = "sftp#{i}"
  priv = File.join(KEYS_DIR, name)
  pub  = "#{priv}.pub"
  unless File.exist?(priv) && File.exist?(pub)
    if system('ssh-keygen', '-t', 'ed25519', '-f', priv, '-N', '', '-C', "#{name}@vagrant")
      warn "[vagrant] the keys are generated!!!"
      FileUtils.chmod 0o600, priv, pub
    else
      warn "[vagrant] Warning: ssh-keygen failed for #{name}; you may need to generate keys manually."
    end
  end
end

Vagrant.configure('2') do |config|
  config.vm.box = 'ubuntu/jammy64'
  config.vm.boot_timeout = 300

  # Mount host keys read-only
  config.vm.synced_folder KEYS_DIR, '/vagrant/keys', owner: 'root', group: 'root', mount_options: ['ro', 'dmode=700', 'fmode=600']

  # Global SSH config hardening
  config.vm.provision 'shell', path: 'scripts/provision_global_ssh.sh'

  (1..3).each do |i|
    config.vm.define "sftp#{i}" do |vm|
      vm.vm.hostname = "sftp#{i}"
      vm.vm.network  'private_network', ip: "192.168.56.10#{i}"
      vm.vm.network  'forwarded_port', guest: 22, host: 4000 + i

      vm.vm.provider 'virtualbox' do |vb|
        vb.gui = true # TODO: true
        vb.memory = 5120
        vb.cpus   = 4
        vb.customize ['modifyvm', :id, '--uartmode1', 'disconnected']
        vb.customize ['modifyvm', :id, '--uartmode2', 'disconnected']
      end

      vm.vm.provision 'shell', path: 'scripts/provision_sftp_node.sh'

      vm.vm.provision 'file', source: 'scripts/generate.sh', destination: '/tmp/generate.sh'
      vm.vm.provision 'shell', inline: <<-SHELL
        mv /tmp/generate.sh /home/sftpuser/generate.sh
        chmod 750 /home/sftpuser/generate.sh
        chown sftpuser:sftpuser /home/sftpuser/generate.sh
        (crontab -u sftpuser -l 2>/dev/null; echo "*/5 * * * * /home/sftpuser/generate.sh") | crontab -u sftpuser -
      SHELL

      # private key is put
      vm.vm.provision 'file', source: "keys/sftp#{i}", destination: "~/.ssh/id_ed25519"
      #vm.vm.provision "shell", inline: "install -o sftpuser -g sftpuser -m 600 .ssh/id_ed25519 ../sftpuser/.ssh/id_ed25519"

      # public key
      (1..3).each do |iterator|
        vm.vm.provision "file", source: "keys/sftp#{iterator}.pub", destination: "/tmp/id_ed25519_#{iterator}.pub"
      end
    end
  end
end