FROM postgres:16-bookworm

# Install openssh-server
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    && rm -rf /var/lib/apt/lists/*

# Create osiris user with access to pg_dump
RUN useradd -m -s /bin/bash osiris \
    && usermod -aG postgres osiris \
    && usermod -p '*' osiris \
    && mkdir -p /home/osiris/.ssh \
    && chown -R osiris:osiris /home/osiris/.ssh \
    && chmod 700 /home/osiris/.ssh

# Ensure sshd runtime directory exists
RUN mkdir -p /run/sshd

# Copy sshd config
COPY sshd_config /etc/ssh/sshd_config

# Copy seed data
COPY seed.sql /docker-entrypoint-initdb.d/seed.sql

COPY entrypoint.sh /entrypoint-wrapper.sh
RUN chmod +x /entrypoint-wrapper.sh

ENTRYPOINT ["/entrypoint-wrapper.sh"]
CMD ["postgres"]
