FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# 1. Base system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    slurm-wlm \
    munge \
    python3 \
    python3-venv \
    python3-pip \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# 2. Complete, standalone SSH daemon configuration
RUN mkdir -p /var/run/sshd /run/sshd /etc/ssh && \
    cat <<'EOF' > /etc/ssh/sshd_config
Port 22
HostKey /etc/ssh/ssh_host_rsa_key
HostKey /etc/ssh/ssh_host_ecdsa_key
HostKey /etc/ssh/ssh_host_ed25519_key

PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys
PasswordAuthentication no
KbdInteractiveAuthentication no
UsePAM no
X11Forwarding no
PrintMotd no
PrintLastLog no
AcceptEnv LANG LC_*
Subsystem sftp internal-sftp
StrictModes no
LogLevel DEBUG
EOF

# 3. Pre-generate SSH host keys & munge key
RUN ssh-keygen -A && \
    mkdir -p /var/run/munge /var/lib/munge /var/log/munge /etc/munge && \
    dd if=/dev/urandom of=/etc/munge/munge.key bs=1024 count=1 status=none && \
    chown -R munge:munge /etc/munge /var/run/munge /var/lib/munge /var/log/munge && \
    chmod 0700 /etc/munge /var/lib/munge /var/log/munge && \
    chmod 0755 /var/run/munge && \
    chmod 0600 /etc/munge/munge.key

# 4. Install uv and build Python 3.12 virtualenv with all base dependencies baked into image
# Note: usermod -p '*' unlocks the shadow password field so OpenSSH allows publickey login with UsePAM no
RUN pip install --no-cache-dir uv && \
    (id -u ubuntu >/dev/null 2>&1 || useradd -m -s /bin/bash ubuntu) && \
    usermod -p '*' ubuntu && \
    mkdir -p /home/ubuntu/.ssh /tmp/aiida_run && \
    chmod 0700 /home/ubuntu/.ssh && \
    chown -R ubuntu:ubuntu /home/ubuntu /tmp/aiida_run && \
    su - ubuntu -c "uv venv --python 3.12 /home/ubuntu/venv && \
    uv pip install --python /home/ubuntu/venv \
        'aiida-core>=2.6,<3' \
        'aiida-pythonjob~=0.5.2' \
        'euphonic[phonopy-reader]~=2.0' \
        'seekpath>=2.2.1,<3' \
        'abinslib==0.1.*' \
        'resins~=0.1.0'"

# 5. Pre-bake authorized SSH key
COPY id_rsa.pub /home/ubuntu/.ssh/authorized_keys
RUN chmod 0600 /home/ubuntu/.ssh/authorized_keys && \
    chown -R ubuntu:ubuntu /home/ubuntu /tmp/aiida_run && \
    chmod 0777 /tmp/aiida_run

# 6. Slurm configuration & entrypoint
COPY slurm.conf /etc/slurm/slurm.conf
COPY cgroup.conf /etc/slurm/cgroup.conf
RUN mkdir -p /var/spool/slurmctld /var/spool/slurmd /var/log/slurm /var/run/slurm /run/slurm && \
    chown -R slurm:slurm /var/spool/slurmctld /var/spool/slurmd /var/log/slurm /etc/slurm

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22
ENTRYPOINT ["/entrypoint.sh"]
