FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# 1. Base system dependencies
# python3-pip / python3-venv are deliberately absent: uv is copied in from its
# published image (step 4) and provisions its own CPython, so nothing here needs
# the system pip or venv module. `sudo` is absent because nothing invokes it.
# ca-certificates is named explicitly rather than inherited from python3-pip's
# dependency tree, so uv's HTTPS downloads do not rely on a transitive package.
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    slurm-wlm \
    munge \
    python3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 2. Complete, standalone SSH daemon configuration
RUN mkdir -p /var/run/sshd /run/sshd /etc/ssh
COPY tests/container/sshd_config /etc/ssh/sshd_config

# 3. Pre-generate SSH host keys & munge key
RUN ssh-keygen -A && \
    mkdir -p /var/run/munge /var/lib/munge /var/log/munge /etc/munge && \
    dd if=/dev/urandom of=/etc/munge/munge.key bs=1024 count=1 status=none && \
    chown -R munge:munge /etc/munge /var/run/munge /var/lib/munge /var/log/munge && \
    chmod 0700 /etc/munge /var/lib/munge /var/log/munge && \
    chmod 0755 /var/run/munge && \
    chmod 0600 /etc/munge/munge.key

# 4. Install uv and build Python 3.12 virtualenv with all base dependencies baked into image
# uv comes from its published image rather than `pip install uv`, which removes
# the only reason this image needed python3-pip.
# `--no-cache` keeps uv's wheel cache out of the layer: it is written during the
# install and is of no use afterwards in a single-purpose image.
# Note: usermod -p '*' unlocks the shadow password field so OpenSSH allows publickey login with UsePAM no
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv

# Copy the dependency manifest and the vendored-wheel directory before
# installing. The build context is the project root, so paths are relative to
# that. `COPY <dir> <dest>` copies the directory's *contents*, so wheels/ needs
# its own destination path to survive as a directory rather than being flattened
# into /tmp/deps.
#
# The layout matters: uv only reads `[tool.uv] find-links = ["wheels"]` when it
# discovers pyproject.toml as the enclosing project, i.e. from the working
# directory -- not from the path given to `-r`. The install below therefore runs
# from /tmp/deps, so find-links resolves to /tmp/deps/wheels and a vendored
# aarch64 Euphonic wheel is honoured exactly as it is on the host. Empty on
# x86-64, where every dependency comes from PyPI.
COPY pyproject.toml /tmp/deps/pyproject.toml
COPY wheels /tmp/deps/wheels

RUN (id -u ubuntu >/dev/null 2>&1 || useradd -m -s /bin/bash ubuntu) && \
    usermod -p '*' ubuntu && \
    mkdir -p /home/ubuntu/.ssh /tmp/aiida_run && \
    chmod 0700 /home/ubuntu/.ssh && \
    chown -R ubuntu:ubuntu /home/ubuntu /tmp/aiida_run && \
    su - ubuntu -c "uv venv --no-cache --python 3.12 /home/ubuntu/venv && \
    cd /tmp/deps && \
    uv pip install --no-cache --python /home/ubuntu/venv -r pyproject.toml"

# 5. Pre-bake authorized SSH key
# Build context is the project root; COPY paths are tests/container/-relative
COPY tests/container/id_rsa.pub /home/ubuntu/.ssh/authorized_keys
RUN chmod 0600 /home/ubuntu/.ssh/authorized_keys && \
    chown ubuntu:ubuntu /home/ubuntu/.ssh/authorized_keys && \
    chmod 0777 /tmp/aiida_run

# 6. Slurm configuration & entrypoint
# Build context is the project root; COPY paths are tests/container/-relative
COPY tests/container/slurm.conf /etc/slurm/slurm.conf
RUN mkdir -p /var/spool/slurmctld /var/spool/slurmd /var/log/slurm /var/run/slurm /run/slurm && \
    chown -R slurm:slurm /var/spool/slurmctld /var/spool/slurmd /var/log/slurm /etc/slurm

COPY tests/container/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22
ENTRYPOINT ["/entrypoint.sh"]
