#!/bin/bash
set -e

# Pre-removal script for Osiris

case "$1" in
    remove|upgrade|deconfigure)
        # Stop timer and service if active
        if systemctl is-active --quiet osiris-backup.timer 2>/dev/null; then
            systemctl stop osiris-backup.timer || true
        fi

        if systemctl is-active --quiet osiris-backup.service 2>/dev/null; then
            systemctl stop osiris-backup.service || true
        fi
        ;;

    failed-upgrade)
        ;;

    *)
        echo "prerm called with unknown argument: $1" >&2
        exit 1
        ;;
esac

exit 0
