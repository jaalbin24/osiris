# Environment Configuration

Osiris uses the `OSIRIS_ENV` environment variable to determine the runtime environment. This affects file paths, logging behavior, and other environment-specific settings.

## Environments

| Environment | Description |
|-------------|-------------|
| `production` | Default. Uses system paths (`/etc/osiris/`, `/var/log/osiris/`, etc.) |
| `development` | Uses paths relative to config file for local development |
| `test` | Uses paths relative to config file, optimized for automated testing |

## Setting the Environment

### Production (default)

No configuration needed. When `OSIRIS_ENV` is unset, Osiris defaults to production mode.

```bash
# These are equivalent:
sudo osiris init --generate-password
OSIRIS_ENV=production sudo osiris init --generate-password
```

### Development

Set `OSIRIS_ENV=development` to use local paths:

```bash
export OSIRIS_ENV=development
osiris --config ./my-config.yaml init --generate-password
```

This creates files relative to the config directory:
- `./repo-password` instead of `/etc/osiris/repo-password`
- `./osiris.log` instead of `/var/log/osiris/osiris.log`
- `./cache/` instead of `/var/cache/osiris/`

### Test

For automated tests, set `OSIRIS_ENV=test`. In pytest, this is handled automatically by the `set_test_environment` fixture in `conftest.py`:

```python
@pytest.fixture(autouse=True)
def set_test_environment(monkeypatch):
    monkeypatch.setenv("OSIRIS_ENV", "test")
```

## Path Behavior by Environment

| Path | Production | Development/Test |
|------|------------|------------------|
| Config | `/etc/osiris/config.yaml` | `{config_dir}/config.yaml` |
| Password | `/etc/osiris/repo-password` | `{config_dir}/repo-password` |
| SSH key | `/etc/osiris/ssh/id_ed25519` | `{config_dir}/ssh/id_ed25519` |
| Log file | `/var/log/osiris/osiris.log` | `{config_dir}/osiris.log` |
| Cache | `/var/cache/osiris/` | `{config_dir}/cache/` |
| Run dir | `/run/osiris/` | `{config_dir}/run/` |

## Using in Code

```python
from osiris.env import get_environment, is_production, is_test, is_local

# Get the current environment
env = get_environment()  # Returns "production", "development", or "test"

# Check specific environments
if is_production():
    # Use system paths, production logging, etc.
    ...

if is_test():
    # Skip external service calls, use mocks, etc.
    ...

if is_local():
    # True for both "development" and "test"
    # Use relative paths, verbose logging, etc.
    ...
```

## Systemd Service

The systemd service runs in production mode by default. The environment is not set in the service file, so it uses the default:

```ini
# /etc/systemd/system/osiris-backup.service
[Service]
Type=oneshot
ExecStart=/usr/local/bin/osiris backup --non-interactive --force
# OSIRIS_ENV defaults to "production"
```

## Invalid Environment Values

If `OSIRIS_ENV` is set to an invalid value, Osiris will:
1. Log a warning
2. Fall back to `production` for safety

```bash
$ OSIRIS_ENV=invalid osiris status
# Warning: Invalid OSIRIS_ENV='invalid', expected one of {'production', 'development', 'test'}. Defaulting to 'production'.
```
