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
