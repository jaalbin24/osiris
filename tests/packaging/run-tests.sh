#!/bin/bash
# Packaging integration tests — runs inside Vagrant VM as root
set -euo pipefail

PASS=0
FAIL=0

pass() { echo "  PASS: $1"; ((PASS++)); }
fail() { echo "  FAIL: $1"; ((FAIL++)); }

check() {
    local desc="$1"; shift
    if "$@" > /dev/null 2>&1; then
        pass "$desc"
    else
        fail "$desc"
    fi
}

check_not() {
    local desc="$1"; shift
    if "$@" > /dev/null 2>&1; then
        fail "$desc"
    else
        pass "$desc"
    fi
}

DEB=$(ls /dist/osiris_*.deb 2>/dev/null | head -1)
if [ -z "$DEB" ]; then
    echo "ERROR: No .deb found in /dist/"
    exit 1
fi

echo "Testing: $DEB"
echo ""

# ── Phase 1: Install ────────────────────────────────────────────────
echo "Phase 1: Install"

apt-get install -y -qq "$DEB" > /dev/null 2>&1
check "Package installed" dpkg -s osiris
check "Binary in PATH" which osiris
check "osiris --help works" osiris --help
check_not "'service' subcommand is gone" osiris service --help

echo ""

# ── Phase 2: Systemd ────────────────────────────────────────────────
echo "Phase 2: Systemd"

check "Service unit in /lib/systemd/system" test -f /lib/systemd/system/osiris-backup.service
check "Timer unit in /lib/systemd/system" test -f /lib/systemd/system/osiris-backup.timer
check "Timer is enabled" systemctl is-enabled osiris-backup.timer
check_not "Timer is not active (no config yet)" systemctl is-active osiris-backup.timer

echo ""

# ── Phase 3: Init + trigger ─────────────────────────────────────────
echo "Phase 3: Init + trigger"

osiris init --generate-password --non-interactive > /dev/null 2>&1
check "Config created" test -f /etc/osiris/config.yaml

systemctl start osiris-backup.timer
check "Timer is active after start" systemctl is-active osiris-backup.timer

# Trigger the service manually (will fail since no real targets, but should
# produce journal output proving the unit runs)
systemctl start osiris-backup.service 2>/dev/null || true
check "Journal has osiris entries" journalctl -u osiris-backup.service --no-pager -q -n 1

echo ""

# ── Phase 4: Removal ────────────────────────────────────────────────
echo "Phase 4: Removal"

apt-get remove -y -qq osiris > /dev/null 2>&1
check_not "Timer is not active" systemctl is-active osiris-backup.timer
check_not "Timer is not enabled" systemctl is-enabled osiris-backup.timer
check_not "Service unit removed" test -f /lib/systemd/system/osiris-backup.service
check_not "Timer unit removed" test -f /lib/systemd/system/osiris-backup.timer
check_not "Binary removed" which osiris

echo ""

# ── Summary ──────────────────────────────────────────────────────────
TOTAL=$((PASS + FAIL))
echo "Results: $PASS/$TOTAL passed"

if [ "$FAIL" -gt 0 ]; then
    echo "FAILED"
    exit 1
fi

echo "ALL PASSED"
