require 'fileutils'

Vagrant.configure('2') do |config|
  config.vm.box = 'ubuntu/jammy64'
  config.vm.boot_timeout = 300

  (1..3).each do |i|
    config.vm.define "sftp#{i}" do |vm|
      vm.vm.hostname = "sftp#{i}"
      vm.vm.network  'private_network', ip: "192.168.56.10#{i}"
      vm.vm.network  'forwarded_port', guest: 22, host: 4000 + i, auto_correct: true

      vm.vm.synced_folder "./collected_sftp_files/sftp#{i}_uploads",  
                          "/home/sftpuser/upload",                   
                          create: true,                              
                          type: "virtualbox"                         


      vm.vm.provider 'virtualbox' do |vb|
        vb.gui = true 
        vb.memory = 4024 
        vb.cpus   = 4     
        vb.customize ['modifyvm', :id, '--uartmode1', 'disconnected']
        vb.customize ['modifyvm', :id, '--uartmode2', 'disconnected']
      end

      vm.vm.provision 'basic_setup', type: 'shell', path: 'scripts/basic_setup.sh', run: "never", env: {"SFTP_PASSWORD" => "verystrongpassword1"}

      config.vm.provision "generate_ssh_key", type: "shell", path: "scripts/generate_ssh_key.sh", run: "never", env: {"SFTP_USERNAME" => "192.168.56.10#{i}"}
      config.vm.provision "exchange_keys", type: "shell", path: "scripts/exchange_keys.sh", run: "never", env: {"SFTP_USERNAME" => "sftpuser", "SFTP_PASSWORD" => "verystrongpassword1", "SFTP_IP_1" => "192.168.56.101", "SFTP_IP_2" => "192.168.56.102", "SFTP_IP_3" => "192.168.56.103"}
  
      config.vm.provision 'provision_global_ssh', type: 'shell', path: 'scripts/provision_global_ssh.sh', run: "never"

      vm.vm.provision 'provision_sftp_node', type: 'shell', path: 'scripts/provision_sftp_node.sh', run: "never"
      vm.vm.provision 'run_rkhunter', type: 'shell', path: 'scripts/run_rkhunter.sh', run: "never"

      vm.vm.provision 'generate_copy', type: 'file', source: 'scripts/generate.sh', destination: '/tmp/generate.sh', run: "never"
      vm.vm.provision 'final_setup', type: 'shell', path: 'scripts/final_setup.sh', run: "never"
    end
  end
end