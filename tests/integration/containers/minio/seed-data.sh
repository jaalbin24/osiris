#!/bin/bash
set -euo pipefail

# Wait for MinIO to be healthy
echo "==> Waiting for MinIO to start..."
TIMEOUT=60
ELAPSED=0
while ! curl -sf http://localhost:9000/minio/health/live >/dev/null 2>&1; do
    sleep 1
    ELAPSED=$((ELAPSED + 1))
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        echo "ERROR: Timed out waiting for MinIO"
        exit 1
    fi
done

echo "==> Seeding MinIO test data..."

# Create test bucket directory structure (MinIO uses filesystem layout)
BUCKET_DIR="/var/lib/minio/data/test-bucket"
mkdir -p "$BUCKET_DIR/subdir"

# Create JSON data files
cat > "$BUCKET_DIR/data-001.json" <<'EOF'
{"id": 1, "name": "alpha", "tags": ["test", "seed"], "timestamp": "2026-01-15T10:00:00Z"}
EOF

cat > "$BUCKET_DIR/data-002.json" <<'EOF'
{"id": 2, "name": "beta", "tags": ["test", "seed"], "timestamp": "2026-01-15T10:05:00Z"}
EOF

# Create a 64KB binary blob
dd if=/dev/urandom of="$BUCKET_DIR/binary-blob.bin" bs=1024 count=64 2>/dev/null

# Create nested file
echo "This is a nested test file for rsync backup verification." > "$BUCKET_DIR/subdir/nested.txt"

# Set ownership
chown -R minio:minio "$BUCKET_DIR"

echo "==> MinIO seed data ready"
