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
## Running Application with PostgreSQl using Docker-Compose 
After all virtual machines are provisioned and SFTP exchange is running, you can launch the log analysis web application using Docker Compose.
### 1. Navigate to the application directory
```bash
cd flask_reporter
```
### 2. Build and run the containers
This command will build the Flask application and start both the app and PostgreSQL services.
```bash
docker compose up --build
```
### 3. Access the web interface
You will see a web dashboard with statistics on file exchanges between SFTP servers.
```bash
http://127.0.0.1:5001/
```
## Alternative: Use Pre-Built Docker Image from Docker Hub
The application image is also available on Docker Hub and can be pulled directly
```bash
docker pull vladushaaaa/flask_reporter-app
```
## To Stop the Application
```bash
docker compose down
```
## Additional notes
- All provisioning scripts are designed to be idempotent — you can re-run them safely if needed.
- You can verify that the file exchange and reporting processes are working correctly by checking the synchronized folder `../collected_sftp_files` on the host machine. It reflects the contents of the `/collected_sftp_files` directory from inside the container.
- PostgreSQL data is stored in a Docker volume by default; removing the volume will reset the database state.
## Troubleshooting
- If a `Timed out` error occurs during `vagrant up` or `vagrant provision`, re-run the command specifically for the affected VM (e.g., `vagrant up sftp2`).
- In case of SSH connection problems, verify that:
  - The sftpuser account was created successfully on all VMs.
  - SSH keys were generated and exchanged properly.
  - Permissions for `.ssh` folders and `authorized_keys` are correct.
- If Docker Compose services fail, check for port conflicts (e.g., `ports 5001`, `5433`) or stale volumes.
