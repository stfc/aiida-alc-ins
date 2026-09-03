#!/bin/bash

echo "[slurm-container] Configuring Slurm host and hardware..."
HOST=$(hostname)
CPUS=$(nproc 2>/dev/null || echo 1)

sed -i "s/<<HOSTNAME>>/${HOST}/g" /etc/slurm/slurm.conf
sed -i "s/<<CPU>>/${CPUS}/g" /etc/slurm/slurm.conf

# Ensure runtime and log directories exist; world-readable logs for test diagnostics
mkdir -p /var/run/sshd /run/sshd /tmp/aiida_run /var/log/slurm /var/spool/slurmctld /var/spool/slurmd
touch /var/log/slurm/slurmctld.log /var/log/slurm/slurmd.log
chmod 0644 /var/log/slurm/*.log

echo "[slurm-container] Starting Slurm & Munge daemons..."
service munge start
service slurmctld start
sleep 1
service slurmd start
sleep 1

# Resume node state to IDLE
scontrol update NodeName=${HOST} State=RESUME 2>/dev/null || true

echo "[slurm-container] Starting OpenSSH server in foreground..."
exec /usr/sbin/sshd -D -e
