## Why

`aiida-pythonjob` executes Python functions on remote compute nodes by reference (`operations.py` cloudpickled into a remote environment), but current unit tests exercise jobs exclusively on `localhost` using the current interpreter. Adding an automated integration test running against an SSH-accessible Slurm cluster emulates a real HPC execution environment in local development and GitHub Actions CI.

## What Changes

- Introduce containerized Slurm test infrastructure using a lightweight Python engine helper that auto-detects `podman` or `docker` and launches `xenonmiddleware/slurm`.
- Bind the container's OpenSSH server strictly to a local ephemeral port (`127.0.0.1::22`) to guarantee no wider network exposure or port collisions.
- Generate throwaway RSA keypairs in-memory using `paramiko` for cross-platform SSH authentication without relying on system `ssh-keygen`.
- Mount the workspace read-only (`/workspace:ro`) into the container and install the package into a remote virtualenv (`/home/ubuntu/venv`).
- Provide AiiDA `Computer` (`core.ssh` + `core.slurm`) and `InstalledCode` Pytest fixtures in `tests/conftest.py`.
- Register the `@pytest.mark.containerized` Pytest marker in `pyproject.toml`.
- Auto-skip containerized integration tests gracefully when neither `podman` nor `docker` is available or when `-m "not containerized"` is specified.
- Integrate the containerized tests into the main `pytest` step in GitHub Actions CI (`.github/workflows/ci.yml`).

## Non-goals

- Replacing fast local unit tests for day-to-day TDD iteration.
- Testing non-Slurm batch schedulers (such as PBS Pro, LSF, or Torque).
- Running a separate or multi-node Slurm cluster; a single-node containerized Slurm instance is sufficient.
- Exposing the container's SSH server to external network interfaces beyond `127.0.0.1`.

## Capabilities

### New Capabilities

*(None)*

### Modified Capabilities

- `testing-and-ci`: Add requirements for containerized SSH + Slurm integration testing, engine auto-detection, `@pytest.mark.containerized` marker registration, and graceful auto-skipping when container runtimes are absent.

## Impact

- `pyproject.toml`: Register `containerized` Pytest marker under `[tool.pytest.ini_options]`.
- `tests/conftest.py`: Add `container_engine`, `slurm_container`, `slurm_computer`, and `slurm_python_code` fixtures.
- `tests/slurm_support.py`: Add container lifecycle management and Paramiko key generation helper module.
- `tests/test_remote_slurm.py`: Add end-to-end integration test running a WorkChain on the remote Slurm container.
- `.github/workflows/ci.yml`: Ensure Docker container execution runs as part of standard CI test workflow.
