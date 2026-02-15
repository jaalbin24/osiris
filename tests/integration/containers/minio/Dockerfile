FROM debian:bookworm-slim

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    curl \
    ca-certificates \
    rsync \
    && rm -rf /var/lib/apt/lists/*

# Download MinIO server and mc client
RUN curl -fsSL https://dl.min.io/server/minio/release/linux-amd64/minio -o /usr/local/bin/minio \
    && chmod +x /usr/local/bin/minio \
    && curl -fsSL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc \
    && chmod +x /usr/local/bin/mc

# Create minio user (service owner)
RUN useradd -r -s /usr/sbin/nologin minio

# Create osiris user (backup operator) and add to minio group
RUN useradd -m -s /bin/bash osiris \
    && usermod -p '*' osiris \
    && usermod -aG minio osiris \
    && mkdir -p /home/osiris/.ssh \
    && chown -R osiris:osiris /home/osiris/.ssh \
    && chmod 700 /home/osiris/.ssh

# Create MinIO data directory (owned by minio, group-writable for osiris)
RUN mkdir -p /var/lib/minio/data \
    && chown -R minio:minio /var/lib/minio \
    && chmod -R g+rwX /var/lib/minio \
    && chmod g+s /var/lib/minio/data

# Ensure sshd runtime directory exists
RUN mkdir -p /run/sshd

# Copy config files
COPY sshd_config /etc/ssh/sshd_config
COPY seed-data.sh /seed-data.sh
RUN chmod +x /seed-data.sh

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# MinIO environment
ENV MINIO_ROOT_USER=minioadmin
ENV MINIO_ROOT_PASSWORD=minioadmin

EXPOSE 9000 9001

ENTRYPOINT ["/entrypoint.sh"]
