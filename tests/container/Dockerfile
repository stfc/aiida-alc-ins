FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# 1. Base system dependencies
# OpenSSH server for core.ssh transport, ca-certificates + curl for fetching uv and hq,
# and python3 as the base system interpreter.
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    python3 \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. Complete, standalone SSH daemon configuration
RUN mkdir -p /var/run/sshd /run/sshd /etc/ssh
COPY tests/container/sshd_config /etc/ssh/sshd_config

# 3. Pre-generate SSH host keys
RUN ssh-keygen -A

# 4. Install HyperQueue standalone binary
# Detect architecture and fetch official standalone release tarball
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then \
        HQ_ARCH="linux-x64"; \
    elif [ "$ARCH" = "aarch64" ]; then \
        HQ_ARCH="linux-arm64-linux"; \
    else \
        echo "Unsupported arch: $ARCH" && exit 1; \
    fi && \
    curl -fsSL "https://github.com/It4innovations/hyperqueue/releases/download/v0.20.0/hq-v0.20.0-${HQ_ARCH}.tar.gz" | tar -xz -C /usr/local/bin && \
    chmod +x /usr/local/bin/hq

# 5. Install uv from official published image
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv

# 6. Copy project manifest, source, and vendored wheels
# Build context is project root; /tmp/deps layout preserves find-links = ["wheels"]
COPY pyproject.toml README.md LICENSE /tmp/deps/
COPY wheels /tmp/deps/wheels
COPY src /tmp/deps/src

# 7. Create ubuntu user and build AiiDA-free Python 3.12 virtualenv
# - Non-editable install of package into /home/ubuntu/venv
# - Uninstalls aiida-core and aiida-pythonjob to enforce lean remote contract
# - Verifies operations imports cleanly while aiida is absent
RUN (id -u ubuntu >/dev/null 2>&1 || useradd -m -s /bin/bash ubuntu) && \
    usermod -p '*' ubuntu && \
    mkdir -p /home/ubuntu/.ssh /home/ubuntu/.hq-server /tmp/aiida_run && \
    chmod 0700 /home/ubuntu/.ssh /home/ubuntu/.hq-server && \
    touch /home/ubuntu/.ssh/authorized_keys && \
    chmod 0600 /home/ubuntu/.ssh/authorized_keys && \
    chown -R ubuntu:ubuntu /home/ubuntu /tmp/aiida_run && \
    chmod 0777 /tmp/aiida_run && \
    su - ubuntu -c "uv venv --no-cache --python 3.12 /home/ubuntu/venv && \
    cd /tmp/deps && \
    uv pip install --no-cache --python /home/ubuntu/venv . && \
    uv pip uninstall --python /home/ubuntu/venv aiida-core aiida-pythonjob && \
    /home/ubuntu/venv/bin/python -c 'import aiida_pythonjob_ins.operations; import sys; assert \"aiida\" not in sys.modules'"

COPY tests/container/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22
ENTRYPOINT ["/entrypoint.sh"]
