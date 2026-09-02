"""Container and Slurm helper utilities for remote SSH/Slurm integration tests."""

from __future__ import annotations

import contextlib
import logging
import shutil
import socket
import subprocess
import time
import uuid
from typing import TYPE_CHECKING

import paramiko

if TYPE_CHECKING:
    from pathlib import Path

LOCAL_IMAGE_TAG = "aiida-slurm-test:latest"


def detect_container_engine() -> str | None:
    """Return 'podman' or 'docker' if installed and operational, else None."""
    for engine in ("podman", "docker"):
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
    """Ensure the local Slurm test container image is built.

    The build context is the project root, allowing the Dockerfile to COPY
    pyproject.toml and wheels/ directly. The Dockerfile path is passed
    explicitly via -f, making COPY sources relative to tests/container/.
    """
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


def find_free_port() -> int:
    """Find an available unprivileged host port on loopback."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class SlurmContainer:
    """Manages an ephemeral Slurm container built from tests/container/Dockerfile."""

    def __init__(self, engine: str, project_root: Path, key_dir: Path):
        self.engine = engine
        self.project_root = project_root
        self.key_dir = key_dir
        self.container_name = f"aiida-slurm-test-{uuid.uuid4().hex[:8]}"
        self.container_id: str | None = None
        self.host_port: int | None = None
        self.ssh_key_file: Path | None = None

    def start(self, timeout: float = 120.0) -> None:
        """Launch the container and wait for SSH & Slurm readiness."""
        # 0. Ensure container image is built
        image_tag = ensure_container_image(self.engine, self.project_root)

        # 1. Use the pre-baked test SSH private key
        src_key = self.project_root / "tests" / "container" / "id_rsa"
        dst_key = self.key_dir / "id_rsa"
        shutil.copy(src_key, dst_key)
        dst_key.chmod(0o600)
        self.ssh_key_file = dst_key

        # 2. Launch container with dynamic port forward
        self.host_port = find_free_port()
        cmd = [
            self.engine,
            "run",
            "-d",
            "--name",
            self.container_name,
            "-p",
            f"127.0.0.1:{self.host_port}:22",
            "-v",
            f"{self.project_root.resolve()}:/workspace:ro",
            image_tag,
        ]
        self.container_id = subprocess.check_output(cmd).decode().strip()

        # 3. Verify container started and stays running
        time.sleep(0.5)
        inspect_state = subprocess.run(
            [self.engine, "inspect", "-f", "{{.State.Running}}", self.container_id],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        if inspect_state != "true":
            cid = self.container_id
            logs = subprocess.run(
                [self.engine, "logs", cid],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            ).stdout
            self.stop()
            msg = (
                f"Container {cid} exited prematurely on startup.\n"
                f"Container logs:\n{logs}"
            )
            raise RuntimeError(msg)

        # 4. Poll for SSH and Slurm readiness over SSH protocol directly
        # Give SSH daemon a moment to initialize before first connection attempt
        time.sleep(5)
        start_time = time.time()
        ready = False
        paramiko_logger = logging.getLogger("paramiko.transport")
        old_level = paramiko_logger.level
        paramiko_logger.setLevel(logging.CRITICAL)

        try:
            while time.time() - start_time < timeout:
                running = subprocess.run(
                    [
                        self.engine,
                        "inspect",
                        "-f",
                        "{{.State.Running}}",
                        self.container_id,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                ).stdout.strip()
                if running != "true":
                    break

                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507
                try:
                    ssh.connect(
                        "127.0.0.1",
                        port=self.host_port,
                        username="ubuntu",
                        key_filename=str(self.ssh_key_file),
                        timeout=2.0,
                    )
                    _, stdout, _ = ssh.exec_command("sinfo -h -o %T")
                    out = stdout.read().decode()
                    if any(s in out for s in ("idle", "alloc")):
                        cmd = "uv pip install --python /home/ubuntu/venv -e /workspace"
                        _, _, stderr = ssh.exec_command(cmd)
                        exit_status = stderr.channel.recv_exit_status()
                        if exit_status == 0:
                            ready = True
                            ssh.close()
                            break
                        err_msg = stderr.read().decode()
                        logging.getLogger("tests.slurm_support").warning(
                            "Workspace pip install failed (exit %s): %s",
                            exit_status,
                            err_msg,
                        )
                    ssh.close()
                except (paramiko.SSHException, OSError):
                    with contextlib.suppress(Exception):
                        ssh.close()
                time.sleep(0.5)
        finally:
            paramiko_logger.setLevel(old_level)

        if not ready:
            cid = self.container_id
            logs = subprocess.run(
                [self.engine, "logs", cid],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            ).stdout
            self.stop()
            msg = (
                f"Container services failed to become ready within {timeout}s.\n"
                f"Container logs:\n{logs}"
            )
            raise RuntimeError(msg)

    def stop(self) -> None:
        """Stop and remove the container."""
        if self.container_id:
            subprocess.run(
                [self.engine, "rm", "-f", self.container_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            self.container_id = None
