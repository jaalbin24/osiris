#!/bin/bash
# Bootstrap a minimal Ubuntu noble rootfs for systemd-nspawn packaging tests.
# Uses noble (24.04) to match the host's Python 3.12 — the .deb bundles a
# venv whose site-packages are tied to the build-time Python minor version.
# Usage: sudo ./bootstrap-rootfs.sh /var/lib/machines/osiris-test-noble
set -euo pipefail

ROOTFS="${1:?Usage: $0 ROOTFS_PATH}"

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: must run as root" >&2
    exit 1
fi

if [ -f "$ROOTFS/etc/os-release" ]; then
    echo "Rootfs already exists at $ROOTFS — skipping"
    exit 0
fi

if ! command -v debootstrap &>/dev/null; then
    echo "Installing debootstrap..."
    apt-get update -qq
    apt-get install -y -qq debootstrap >/dev/null
fi

echo "Bootstrapping Ubuntu noble into $ROOTFS ..."
debootstrap --variant=minbase \
    --components=main,universe \
    --include=systemd,systemd-sysv,dbus,apt,restic,python3 \
    noble "$ROOTFS" http://archive.ubuntu.com/ubuntu

systemd-machine-id-setup --root="$ROOTFS"

echo "Rootfs ready at $ROOTFS"
