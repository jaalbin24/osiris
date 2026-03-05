#!/bin/bash
set -euo pipefail

echo "==> Controller: starting entrypoint"

# 1. Generate SSH keypair if not already present (shared volume)
if [ ! -f /etc/osiris/ssh/id_ed25519 ]; then
    echo "==> Generating SSH keypair..."
    ssh-keygen -t ed25519 -f /etc/osiris/ssh/id_ed25519 -N "" -q
    chmod 600 /etc/osiris/ssh/id_ed25519
    chmod 644 /etc/osiris/ssh/id_ed25519.pub
fi

# 2. Create restic password file
echo "osiris-test-password" > /etc/osiris/repo-password
chmod 600 /etc/osiris/repo-password

# 3. Copy test config into place
cp /build/tests/integration/config/osiris-config.yaml /etc/osiris/config.yaml

# 4. Wait for postgres and minio to be healthy
echo "==> Waiting for postgres..."
TIMEOUT=120
ELAPSED=0
while ! ssh -o BatchMode=yes -o ConnectTimeout=2 -o StrictHostKeyChecking=no \
    -i /etc/osiris/ssh/id_ed25519 osiris@postgres "pg_isready -U postgres" >/dev/null 2>&1; do
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        echo "ERROR: Timed out waiting for postgres"
        exit 1
    fi
done
echo "==> Postgres ready"

echo "==> Waiting for minio..."
ELAPSED=0
while ! ssh -o BatchMode=yes -o ConnectTimeout=2 -o StrictHostKeyChecking=no \
    -i /etc/osiris/ssh/id_ed25519 osiris@minio "curl -sf http://localhost:9000/minio/health/live" >/dev/null 2>&1; do
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        echo "ERROR: Timed out waiting for minio"
        exit 1
    fi
done
echo "==> MinIO ready"

# 5. Initialize restic repo if needed
if ! restic --repo /var/backups/osiris/repo --password-file /etc/osiris/repo-password snapshots >/dev/null 2>&1; then
    echo "==> Initializing restic repository..."
    restic --repo /var/backups/osiris/repo --password-file /etc/osiris/repo-password init
fi

echo "==> Controller ready"

# 6. Signal readiness and execute CMD
touch /tmp/.controller_ready
exec "$@"
