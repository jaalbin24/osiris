#!/bin/bash
set -e

# Post-removal script for Osiris

case "$1" in
    remove|purge)
        if [ -d /run/systemd/system ]; then
            systemctl disable osiris-backup.timer 2>/dev/null || true
            systemctl daemon-reload || true
        fi
        ;;

    upgrade|failed-upgrade|abort-install|abort-upgrade|disappear)
        ;;

    *)
        echo "postrm called with unknown argument: $1" >&2
        exit 1
        ;;
esac

exit 0
