## 1. Project Dependencies & Configuration

- [x] 1.1 Add `aiida-hyperqueue`, `pytest-xdist`, and `filelock` to `[dependency-groups].dev` in `pyproject.toml`, run `uv sync`, and verify imports succeed with `uv run python -c "import aiida_hyperqueue, xdist, filelock"`.
- [x] 1.2 Update `.gitignore` to ensure test session artifacts (`*.lock`, `container_info.json`) are ignored.

## 2. Container Image & Support Utilities

- [x] 2.1 Remove obsolete Slurm configurations and committed keys (`tests/container/slurm.conf`, `tests/container/id_rsa*`, and `tests/slurm_support.py`).
- [x] 2.2 Rebuild `tests/container/Dockerfile` based on `ubuntu:22.04` minimal: install OpenSSH server, download the static `hq` release binary to `/usr/local/bin/hq`, provision `/home/ubuntu/venv` via `uv` from `pyproject.toml` (without `aiida-core` or `aiida-pythonjob`), and configure SSH daemon without static keys.
- [x] 2.3 Create `tests/container/entrypoint.sh` to initialize `hq server` and `hq worker` (detecting available cores via `nproc`, with optional `HQ_CPUS` override) under user `ubuntu`, and launch `sshd` in foreground.
- [x] 2.4 Implement `tests/container_support.py` providing `SSHContainer` management: dynamic port mapping via runtime inspect, session SSH public key injection into `/home/ubuntu/.ssh/authorized_keys`, readiness polling against SSH and `hq status`, and container lifecycle helpers.

## 3. Pytest Fixtures & Multi-Process Coordination

- [x] 3.1 Implement the lazy shared container fixture in `tests/conftest.py` using `FileLock` and `tmp_path_factory.getbasetemp().parent / "container_info.json"`, with single-process bypass when `worker_id == "master"`.
- [x] 3.2 Implement `pytest_collection_modifyitems` in `tests/conftest.py` to sort non-containerized tests ahead of `containerized` tests so unit tests start immediately without waiting for container boot.
- [x] 3.3 Implement `pytest_sessionfinish` in `tests/conftest.py` on the controller process to cleanly stop and remove the shared container at the end of the test session.
- [x] 3.4 Implement `remote_computer` and `remote_python_code` fixtures in `tests/conftest.py` configuring an AiiDA `Computer` (`core.ssh` transport, `hyperqueue` scheduler) and `InstalledCode` pointing at `/home/ubuntu/venv/bin/python`.
- [x] 3.5 Refactor `ssh_key` fixture and `SSHContainer` to use an explicit `SSHKeyPair` dataclass holding both `private_key` and `public_key` paths, removing the implicit public key file side-effect and `.with_suffix(".pub")` filename assumptions.

## 4. Test Suite Implementation

- [x] 4.1 Create `tests/test_remote_ssh.py` (replacing `tests/test_remote_slurm.py`): implement raw transport sanity check (`echo`, directory creation, SFTP upload/download) over `core.ssh`.
- [x] 4.2 Add `PythonJob` execution test on the remote HyperQueue computer in `tests/test_remote_ssh.py` and verify `run_get_node(PythonJob, ...)` completes successfully.
- [x] 4.3 Add workflow integration test (`DosWorkChain`) on the remote HyperQueue computer in `tests/test_remote_ssh.py` and verify end-to-end execution and provenance links.

## 5. Verification & Tooling Parity

- [x] 5.1 Run `uv run ruff check` and `uv run ruff format --check` across `tests/` and verify clean lint and format.
- [x] 5.2 Verify non-containerized unit tests run in parallel with `uv run pytest -m "not containerized" -n auto` and confirm fast execution without container startup.
- [x] 5.3 On an environment with operational Docker/Podman, execute `uv run pytest -m containerized` and `uv run pytest -m containerized -n 2`, verifying parallel test execution against the shared HyperQueue container.
