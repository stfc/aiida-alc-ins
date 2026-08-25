#!/bin/bash
set -x

echo "[slurm-container] Configuring Slurm host and hardware..."
HOST=$(hostname)
CPUS=$(nproc 2>/dev/null || echo 1)
MEMORY=$(if [[ "$(slurmd -C 2>/dev/null)" =~ RealMemory=([0-9]+) ]]; then echo "${BASH_REMATCH[1]}"; else echo "1000"; fi)

sed -i "s/<<HOSTNAME>>/${HOST}/g" /etc/slurm/slurm.conf
sed -i "s/<<CPU>>/${CPUS}/g" /etc/slurm/slurm.conf
sed -i "s/<<MEMORY>>/${MEMORY}/g" /etc/slurm/slurm.conf
chown -R slurm:slurm /etc/slurm

# Ensure runtime and log directories exist with public read permissions for diagnostics
mkdir -p /var/run/sshd /run/sshd /tmp/aiida_run /var/log/slurm /var/spool/slurmctld /var/spool/slurmd
touch /var/log/slurm/slurmctld.log /var/log/slurm/slurmd.log
chown -R slurm:slurm /var/spool/slurmctld /var/spool/slurmd /var/log/slurm
chmod 0755 /var/run/sshd /run/sshd /var/log/slurm
chmod 0644 /var/log/slurm/*.log
chmod 0777 /tmp/aiida_run
chown -R ubuntu:ubuntu /home/ubuntu /tmp/aiida_run

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
