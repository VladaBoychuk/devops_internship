# SFTP Server Setup and Log Analysis Runbook

## Prerequisites 
Before you begin, ensure that your system meets the following requirements:
- [Vagrant](https://developer.hashicorp.com/vagrant/downloads) 
- [VirtualBox](https://www.virtualbox.org/wiki/Downloads) 
- [Git](https://git-scm.com/) 
- [Docker & Docker Compose](https://www.docker.com/products/docker-desktop/)
- [Python 3.10+](https://www.python.org/downloads/release/python-3100/)
- [PostgreSQL](https://www.postgresql.org/download/windows/)

## Setup Steps
### 1. Clone the Repository
```bash
git clone <repository_url>
cd <cloned_repository_folder>
```
### 2. Start the Virtual Machines
```bash
vagrant up
```
### 3. Basic System Setup
Installs essential packages, updates the system, and sets environment variables.
```bash
vagrant provision --provision-with basic_setup
```
### 4. Generate SSH Key for Each VM
Generates SSH key pairs for each VM and stores them under the appropriate user.
```bash
vagrant provision --provision-with generate_ssh_key
```
### 5. Exchange SSH Keys Between VMs
Distributes each VM’s public key to the others and sets up passwordless access.

⚠️ This provisioning step should only be run after all VMs have successfully generated their SSH key pairs (i.e.,`generate_ssh_key` has been executed on each VM). Running it prematurely may result in missing or incomplete key exchange.
```bash
vagrant provision --provision-with exchange_keys
```
### 6. Configure Global SSH Access (Optional)
Sets up key-based access from your local machine to the VMs.
```bash
vagrant provision --provision-with provision_global_ssh
```
### 7. Provision SFTP Server on Each Node
Installs and configures OpenSSH and SFTP subsystem with proper permissions.
```bash
vagrant provision --provision-with provision_sftp_node
```
### 8. Run Security Audit with rkhunter
Scans each VM for known rootkits and common vulnerabilities.
```bash
vagrant provision --provision-with run_rkhunter
```
### 9. Deploy File Exchange Script to VM
Copies the Bash script used to generate timestamped files on neighbor machines.
```bash
vagrant provision --provision-with generate_copy
```
Deploys `generate.sh` to `/tmp/generate.sh` on each VM.

### 10. Final System Configuration
Performs final setup tasks such as restarting services and cleaning up.
```bash
vagrant provision --provision-with final_setup
```
