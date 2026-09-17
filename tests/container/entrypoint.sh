#!/bin/bash
set -e

# 1. Ensure runtime directories exist
mkdir -p /var/run/sshd /run/sshd /tmp/aiida_run
chmod 0777 /tmp/aiida_run

# 2. Determine CPU slots for HyperQueue worker
CPUS=${HQ_CPUS:-$(nproc 2>/dev/null || echo 2)}
echo "[container] Starting HyperQueue server and worker (${CPUS} CPUs)..."

# 3. Start HyperQueue server as unprivileged ubuntu user on loopback
su - ubuntu -c "/usr/local/bin/hq server start --host 127.0.0.1 > /tmp/hq-server.log 2>&1 &"

# Wait up to 10s for HQ server socket to initialize
server_ready=false
for i in $(seq 1 50); do
    if su - ubuntu -c "/usr/local/bin/hq server info" >/dev/null 2>&1; then
        server_ready=true
        break
    fi
    sleep 0.2
done

if [ "$server_ready" != "true" ]; then
    echo "[container] Error: HyperQueue server failed to start:"
    cat /tmp/hq-server.log 2>/dev/null || true
    exit 1
fi

# 4. Start HyperQueue worker with allocated CPUs
su - ubuntu -c "/usr/local/bin/hq worker start --cpus ${CPUS} > /tmp/hq-worker.log 2>&1 &"

# Wait up to 10s for HQ worker to register
worker_ready=false
for i in $(seq 1 50); do
    if su - ubuntu -c "/usr/local/bin/hq worker list" 2>/dev/null | grep -q "RUNNING"; then
        worker_ready=true
        break
    fi
    sleep 0.2
done

if [ "$worker_ready" != "true" ]; then
    echo "[container] Error: HyperQueue worker failed to start:"
    cat /tmp/hq-worker.log 2>/dev/null || true
    exit 1
fi

echo "[container] HyperQueue is operational. Starting OpenSSH server..."
exec /usr/sbin/sshd -D -e
