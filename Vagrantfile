require 'fileutils'

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


  config.vm.synced_folder KEYS_DIR, '/vagrant/keys', owner: 'root', group: 'root', mount_options: ['ro', 'dmode=700', 'fmode=600']

  config.vm.provision 'shell', path: 'scripts/provision_global_ssh.sh'

  (1..3).each do |i|
    config.vm.define "sftp#{i}" do |vm|
      vm.vm.hostname = "sftp#{i}"
      vm.vm.network  'private_network', ip: "192.168.56.10#{i}"
      vm.vm.network  'forwarded_port', guest: 22, host: 4000 + i

      vm.vm.provider 'virtualbox' do |vb|
        vb.gui = true 
        vb.memory = 1024 
        vb.cpus   = 1    
        vb.customize ['modifyvm', :id, '--uartmode1', 'disconnected']
        vb.customize ['modifyvm', :id, '--uartmode2', 'disconnected']
      end

      vm.vm.provision 'shell', path: 'scripts/provision_sftp_node.sh'


      vm.vm.provision 'file', source: 'scripts/generate.sh', destination: '/tmp/generate.sh'
      vm.vm.provision 'shell', inline: <<-SHELL

        if [ -d "/home/sftpuser" ]; then
          mv /tmp/generate.sh /home/sftpuser/generate.sh
          chmod 750 /home/sftpuser/generate.sh
          chown sftpuser:sftpuser /home/sftpuser/generate.sh

          (crontab -u sftpuser -l 2>/dev/null | grep -v -F "/home/sftpuser/generate.sh" ; echo "*/5 * * * * /home/sftpuser/generate.sh") | crontab -u sftpuser -
        else
          echo "Error: /home/sftpuser does not exist. Cannot setup generate.sh" >&2
          exit 1
        fi
      SHELL

    end
  end
end