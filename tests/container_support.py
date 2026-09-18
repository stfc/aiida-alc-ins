"""Container helper utilities for remote SSH/HyperQueue integration tests."""

from __future__ import annotations

import contextlib
import logging
import os
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

import paramiko

if TYPE_CHECKING:
    from pathlib import Path

LOCAL_IMAGE_TAG = "aiida-ssh-hq-test:latest"
logger = logging.getLogger("tests.container_support")


def detect_container_engine() -> str | None:
    """Return 'podman' or 'docker' if installed and operational, else None.

    If the CONTAINER_ENGINE environment variable is set (e.g. 'docker' or 'podman'),
    it takes precedence over auto-detection order.
    """
    configured = os.environ.get("CONTAINER_ENGINE")
    candidates = (configured,) if configured else ("podman", "docker")
    for engine in candidates:
        if shutil.which(engine):
            res = subprocess.run(
                [engine, "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if res.returncode == 0:
                return engine
    return None


def ensure_container_image(engine: str, project_root: Path) -> str:
    """Ensure the local SSH + HyperQueue test container image is built."""
    dockerfile_path = project_root / "tests" / "container" / "Dockerfile"
    res = subprocess.run(
        [
            engine,
            "build",
            "-t",
            LOCAL_IMAGE_TAG,
            "-f",
            str(dockerfile_path),
            str(project_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        msg = (
            f"Failed to build container image '{LOCAL_IMAGE_TAG}'. "
            f"Exit code: {res.returncode}\n"
            f"--- Build Output ---\n{res.stdout}\n{res.stderr}"
        )
        raise RuntimeError(msg)
    return LOCAL_IMAGE_TAG


def query_host_port(engine: str, container_name: str, container_port: int = 22) -> int:
    """Query the runtime-assigned host port published for a container port."""
    cmd = [engine, "port", container_name, f"{container_port}/tcp"]
    out = subprocess.check_output(cmd, text=True).strip()
    if not out:
        msg = (
            f"No port mapping found for {container_name}:{container_port} "
            "(container may have stopped)"
        )
        raise RuntimeError(msg)
    # Output format is typically '127.0.0.1:PORT' or '0.0.0.0:PORT'
    match = re.search(r":(\d+)$", out.splitlines()[0])
    if not match:
        msg = f"Could not parse host port from '{engine} port' output: {out}"
        raise ValueError(msg)
    return int(match.group(1))


@dataclass(frozen=True)
class SSHKeyPair:
    """An ephemeral SSH keypair generated for test sessions."""

    private_key: Path
    public_key: Path

    @property
    def public_key_text(self) -> str:
        """Return the OpenSSH public key line."""
        return self.public_key.read_text().strip()


class SSHContainer:
    """Manages an ephemeral SSH + HyperQueue test container."""

    def __init__(self, engine: str, project_root: Path, keypair: SSHKeyPair) -> None:
        self.engine = engine
        self.project_root = project_root
        self.keypair = keypair
        self.container_name = f"aiida-hq-test-{uuid.uuid4().hex[:8]}"
        self.container_id: str | None = None
        self.host_port: int | None = None

    def start(self, timeout: float = 60.0) -> dict[str, str | int]:
        """Launch container, inject public key, and wait for SSH & HQ readiness."""
        # 1. Ensure image is built
        image_tag = ensure_container_image(self.engine, self.project_root)

        # 2. Verify public key exists
        if not self.keypair.public_key.exists():
            msg = f"Public key not found at {self.keypair.public_key}"
            raise FileNotFoundError(msg)

        # 3. Launch container with dynamic loopback port forward
        cmd = [
            self.engine,
            "run",
            "-d",
            "--name",
            self.container_name,
            "-p",
            "127.0.0.1::22",
            "-v",
            f"{self.keypair.public_key.resolve()}:/home/ubuntu/.ssh/authorized_keys:ro,Z",
            image_tag,
        ]
        self.container_id = subprocess.check_output(cmd, text=True).strip()

        # 4. Verify container started and stays running
        time.sleep(0.5)
        inspect_state = subprocess.run(
            [
                self.engine,
                "inspect",
                "-f",
                "{{.State.Running}}",
                self.container_name,
            ],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        if inspect_state != "true":
            logs = subprocess.run(
                [self.engine, "logs", self.container_name],
                capture_output=True,
                text=True,
                check=False,
            ).stdout
            self.stop()
            msg = (
                f"Container '{self.container_name}' failed to start or "
                f"exited immediately.\nContainer logs:\n{logs}"
            )
            raise RuntimeError(msg)

        # 5. Resolve dynamically assigned host port
        self.host_port = query_host_port(self.engine, self.container_name, 22)

        # 6. Poll for SSH and HyperQueue readiness
        self._wait_for_readiness(timeout)

        return {
            "container_id": self.container_id,
            "container_name": self.container_name,
            "host_port": self.host_port,
            "ssh_key_file": str(self.keypair.private_key),
        }

    def _wait_for_readiness(self, timeout: float) -> None:
        """Poll SSH and HyperQueue service until operational."""
        start_time = time.time()
        paramiko_logger = logging.getLogger("paramiko.transport")
        old_level = paramiko_logger.level
        paramiko_logger.setLevel(logging.CRITICAL)

        ssh_ready = False
        hq_ready = False
        last_error: Exception | None = None

        try:
            while time.time() - start_time < timeout:
                # Check container is still running
                inspect_state = subprocess.run(
                    [
                        self.engine,
                        "inspect",
                        "-f",
                        "{{.State.Running}}",
                        self.container_name,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                ).stdout.strip()
                if inspect_state != "true":
                    break

                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507
                try:
                    ssh.connect(
                        "127.0.0.1",
                        port=self.host_port,
                        username="ubuntu",
                        key_filename=str(self.keypair.private_key),
                        timeout=2.0,
                    )
                    ssh_ready = True

                    # Check HQ server and worker status
                    _, stdout, _ = ssh.exec_command("hq server info && hq worker list")
                    out = stdout.read().decode()
                    if "RUNNING" in out:
                        hq_ready = True
                        ssh.close()
                        break
                    ssh.close()
                except (paramiko.SSHException, OSError) as exc:
                    last_error = exc
                    with contextlib.suppress(Exception):
                        ssh.close()

                time.sleep(0.5)
        finally:
            paramiko_logger.setLevel(old_level)

        if not (ssh_ready and hq_ready):
            logs = subprocess.run(
                [self.engine, "logs", self.container_name],
                capture_output=True,
                text=True,
                check=False,
            ).stdout
            self.stop()
            msg = (
                f"Container services failed to reach readiness within {timeout}s "
                f"(ssh_ready={ssh_ready}, hq_ready={hq_ready}).\n"
                f"Last connection error: {last_error}\n"
                f"Container logs:\n{logs}"
            )
            raise RuntimeError(msg)

    def stop(self) -> None:
        """Stop and remove the container."""
        if self.container_id or self.container_name:
            subprocess.run(
                [self.engine, "rm", "-f", self.container_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            self.container_id = None
