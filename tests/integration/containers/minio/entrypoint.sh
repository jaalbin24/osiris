#!/bin/bash
set -euo pipefail

echo "==> MinIO: starting entrypoint"

# 1. Wait for SSH public key from shared volume (with timeout)
echo "==> Waiting for SSH public key..."
TIMEOUT=60
ELAPSED=0
while [ ! -f /etc/osiris/ssh/id_ed25519.pub ]; do
    sleep 1
    ELAPSED=$((ELAPSED + 1))
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        echo "ERROR: Timed out waiting for SSH public key"
        exit 1
    fi
done

# 2. Install authorized key for osiris user
cp /etc/osiris/ssh/id_ed25519.pub /home/osiris/.ssh/authorized_keys
chown osiris:osiris /home/osiris/.ssh/authorized_keys
chmod 600 /home/osiris/.ssh/authorized_keys

# 3. Generate SSH host keys and start sshd
ssh-keygen -A
/usr/sbin/sshd

# 4. Touch sentinel for health check
touch /tmp/.sshd_ready
echo "==> SSH ready"

# 5. Launch seed script in background (waits for MinIO to be healthy)
/seed-data.sh &

# 6. Exec MinIO server
exec minio server /var/lib/minio/data --console-address ":9001"
