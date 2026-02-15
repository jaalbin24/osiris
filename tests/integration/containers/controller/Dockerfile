FROM python:3.11-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    rsync \
    curl \
    bzip2 \
    && rm -rf /var/lib/apt/lists/* \
    && printf 'Host *\n    StrictHostKeyChecking no\n    UserKnownHostsFile /dev/null\n    LogLevel ERROR\n' >> /etc/ssh/ssh_config

# Install restic (pinned version)
ARG RESTIC_VERSION=0.17.3
RUN curl -fsSL "https://github.com/restic/restic/releases/download/v${RESTIC_VERSION}/restic_${RESTIC_VERSION}_linux_amd64.bz2" \
    | bunzip2 > /usr/local/bin/restic \
    && chmod +x /usr/local/bin/restic

# Install poetry
RUN pip install --no-cache-dir poetry

# Create Osiris directory structure
RUN mkdir -p \
    /etc/osiris/ssh \
    /var/log/osiris \
    /var/cache/osiris \
    /var/backups/osiris/repo \
    /run/osiris

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /app

ENTRYPOINT ["/entrypoint.sh"]
CMD ["sleep", "infinity"]
