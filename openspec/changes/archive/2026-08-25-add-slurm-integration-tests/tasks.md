> **Superseded by [2026-08-26-tidy-slurm-test-infrastructure](../tidy-slurm-test-infrastructure)**
> 
> The following claims in the archived proposal and design do not describe the shipped system:
> - **Base image recommendation**: The archived design recommended `xenonmiddleware/slurm` from Docker Hub (a six-year-old Ubuntu 16.04 build with Python 3.5 and Slurm 17.02) or `ghcr.io/aiidateam/slurm-image` (returns 403 on anonymous pull; other `aiidateam` packages pull successfully). The implementation builds a local image from `tests/container/Dockerfile` instead.
> - **In-memory SSH key generation**: The archived design claimed keys were generated in-memory using paramiko. The implementation uses pre-baked keys committed to `tests/container/id_rsa`.
> - **Engine-assigned port allocation**: The archived design specified `-p 127.0.0.1::22` to let the container engine assign a port. The implementation uses `find_free_port()` in Python and explicit `-p 127.0.0.1:{port}:22`.

## 1. Environment & Config Setup

- [x] 1.1 Register `@pytest.mark.containerized` marker in `pyproject.toml`

## 2. Slurm Support Module & Container Lifecycle

- [x] 2.1 Implement container engine auto-detection (`podman` / `docker`) in `tests/slurm_support.py`
- [x] 2.2 Implement pure-Python RSA keypair generation using `paramiko` in `tests/slurm_support.py`
- [x] 2.3 Implement `SlurmContainer` class in `tests/slurm_support.py` to handle container launch, port mapping, SSH key authorization, remote venv installation, and cleanup

## 3. Pytest Fixtures & Integration Test

- [x] 3.1 Add `container_engine`, `slurm_container`, `slurm_computer`, and `slurm_python_code` fixtures in `tests/conftest.py`
- [x] 3.2 Add containerized integration test `tests/test_remote_slurm.py` marked with `@pytest.mark.containerized`

## 4. Verification & Linting

- [x] 4.1 Verify tests pass via `uv run pytest` and linting passes via `uv run ruff check`
