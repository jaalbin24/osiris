#!/bin/bash
set -e

# Post-installation script for Osiris

case "$1" in
    configure)
        # Create run directory (tmpfs on most systems, may not persist)
        if [ ! -d /run/osiris ]; then
            mkdir -p /run/osiris
            chmod 750 /run/osiris
        fi

        # Reload systemd and enable timer (don't start — no config yet)
        if [ -d /run/systemd/system ]; then
            systemctl daemon-reload || true
            systemctl enable osiris-backup.timer || true
        fi

        echo ""
        echo "Osiris installed successfully."
        echo ""
        echo "Next steps:"
        echo "  1. Run 'sudo osiris init --generate-password' to initialize"
        echo "  2. Edit /etc/osiris/config.yaml to add backup targets"
        echo "  3. Run 'osiris validate' to verify configuration"
        echo "  4. Run 'sudo systemctl start osiris-backup.timer' to activate scheduled backups"
        ;;

    abort-upgrade|abort-remove|abort-deconfigure)
        ;;

    *)
        echo "postinst called with unknown argument: $1" >&2
        exit 1
        ;;
esac

exit 0
