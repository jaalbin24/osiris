#!/bin/bash
# Boot an ephemeral systemd-nspawn container and run packaging tests inside it.
# Usage: sudo ./run-container.sh ROOTFS MACHINE DIST_DIR TEST_DIR
set -euo pipefail

ROOTFS="${1:?Usage: $0 ROOTFS MACHINE DIST_DIR TEST_DIR}"
MACHINE="${2:?Usage: $0 ROOTFS MACHINE DIST_DIR TEST_DIR}"
DIST_DIR="${3:?Usage: $0 ROOTFS MACHINE DIST_DIR TEST_DIR}"
TEST_DIR="${4:?Usage: $0 ROOTFS MACHINE DIST_DIR TEST_DIR}"

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: must run as root" >&2
    exit 1
fi

cleanup() {
    echo "Cleaning up container $MACHINE ..."
    machinectl poweroff "$MACHINE" 2>/dev/null || true
    # Wait briefly for the container to stop
    for _ in $(seq 1 10); do
        machinectl show "$MACHINE" &>/dev/null || break
        sleep 0.5
    done
}
trap cleanup EXIT

# Kill any leftover container with the same name
if machinectl show "$MACHINE" &>/dev/null; then
    echo "Killing leftover container $MACHINE ..."
    machinectl terminate "$MACHINE" 2>/dev/null || true
    sleep 2
fi

echo "Booting ephemeral container $MACHINE ..."
systemd-nspawn \
    --boot \
    --ephemeral \
    --machine="$MACHINE" \
    --directory="$ROOTFS" \
    --bind-ro="$DIST_DIR":/dist \
    --bind-ro="$TEST_DIR":/vagrant \
    --console=pipe \
    --quiet &

# Wait for the container's systemd to finish booting (30s timeout).
# machinectl State=running only means PID 1 is up; we need D-Bus and basic
# services ready before systemd-run can talk to the container.
echo "Waiting for container to boot ..."
for i in $(seq 1 30); do
    sysstate=$(systemctl -M "$MACHINE" is-system-running 2>/dev/null || echo "")
    if [ "$sysstate" = "running" ] || [ "$sysstate" = "degraded" ]; then
        echo "Container ready: $sysstate (${i}s)"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: container did not become ready within 30s (state: $sysstate)" >&2
        exit 1
    fi
    sleep 1
done

echo "Running tests ..."
systemd-run -M "$MACHINE" --wait --pipe /bin/bash /vagrant/run-tests.sh
exit_code=$?

exit "$exit_code"
