echo "Performing initial RKHunter system check on $(hostname)..."
if ! timeout 900 sudo rkhunter --check --sk --append-log --nocolors; then
    echo "Warning: rkhunter --check reported issues, failed or timed out on $(hostname)." >&2
else
    echo "RKHunter initial check completed on $(hostname)."
fi
echo "RKHunter setup and initial check finished on $(hostname)."

echo "SFTP node provisioning finished for $(hostname)."