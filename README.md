# Osiris

CLI backup management tool that wraps restic to provide a simplified, opinionated interface for backing up PostgreSQL databases and MinIO object stores.

## Installation

```bash
poetry install
```

## Usage

```bash
# Initialize repository
osiris init

# Create backup
osiris backup

# List backups
osiris list

# Show backup details
osiris show <batch-id>

# Restore from backup
osiris restore --batch-id <batch-id>

# Check system status
osiris status
```

## Configuration

Configuration is stored at `/etc/osiris/config.yaml`. See the documentation for full configuration options.
