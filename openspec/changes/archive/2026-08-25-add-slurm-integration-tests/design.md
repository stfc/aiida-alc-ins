> **Superseded by [2026-08-26-tidy-slurm-test-infrastructure](../tidy-slurm-test-infrastructure)**
> 
> The following claims in this document do not describe the shipped system:
> - **Base image recommendation**: This design recommended `xenonmiddleware/slurm` from Docker Hub (a six-year-old Ubuntu 16.04 build with Python 3.5 and Slurm 17.02) or `ghcr.io/aiidateam/slurm-image` (returns 403 on anonymous pull; other `aiidateam` packages pull successfully). The implementation builds a local image from `tests/container/Dockerfile` instead.
> - **In-memory SSH key generation**: This design claimed keys were generated in-memory using paramiko. The implementation uses pre-baked keys committed to `tests/container/id_rsa`.
> - **Engine-assigned port allocation**: This design specified `-p 127.0.0.1::22` to let the container engine assign a port. The implementation uses `find_free_port()` in Python and explicit `-p 127.0.0.1:{port}:22`.

## Context

Current tests exercise WorkChains and PythonJobs on `localhost` using the active Python interpreter. To validate true remote execution where `aiida-pythonjob` serializes functions by reference, we need an SSH-accessible Slurm cluster. See `proposal.md` for motivation.

## Goals / Non-Goals

**Goals:**
- Provide a zero-dependency, cross-platform Slurm container fixture supporting both Podman and Docker.
- Configure AiiDA `Computer` (`core.ssh` + `core.slurm`) and `InstalledCode` ORM nodes automatically in Pytest.
- Secure SSH communication to local loopback (`127.0.0.1`) only, with ephemeral port assignment.
- Run integration tests seamlessly in GitHub Actions CI and local development.

**Non-Goals:**
- Supporting non-Slurm schedulers (PBS, LSF, Torque).
- Persisting failed test containers for interactive debugging.
- Exposing container services to wider network interfaces.

## Decisions

### Decision 1: Subprocess-based container engine CLI wrapper (`podman` / `docker`)

Use standard library `shutil.which` and `subprocess` to auto-detect and invoke `podman` or `docker`.

- **Rationale**: Both `podman` and `docker` share identical CLI flags for `run`, `port`, `exec`, `stop`, and `rm`. Invoking the CLI binary directly avoids adding third-party dependencies (`python-on-whales`, `testcontainers`) and bypasses engine socket path quirks across rootless Podman on macOS, Linux, and Windows.
- **Alternatives Considered**:
  - `testcontainers-python`: Requires manual `DOCKER_HOST` socket configuration for rootless Podman.
  - `docker` SDK (`docker-py`): Requires `podman system service` running on Podman.

### Decision 2: Use `xenonmiddleware/slurm` base image

Use `xenonmiddleware/slurm` as the public Slurm single-node image on Docker Hub.

- **Rationale**: Public, unauthenticated Docker Hub image supported across Docker and Podman without registry authentication tokens. Pre-configures `munge`, `slurmctld`, `slurmd`, and `openssh-server`.
- **Alternatives Considered**:
  - `ghcr.io/aiidateam/slurm-image`: Requires GitHub Container Registry bearer authentication token.
  - Custom Containerfile: Adds repository maintenance overhead.

### Decision 3: Pure-Python RSA keypair generation via `paramiko`

Generate throwaway 2048-bit RSA SSH keypairs using `paramiko.RSAKey.generate(2048)`.

- **Rationale**: `paramiko` is a mandatory dependency of `aiida-core`. Generating keys in memory and writing them to Pytest's `tmp_path` avoids relying on system `ssh-keygen`, which is not consistently present in `%PATH%` on Windows or minimal CI runner environments.
- **Alternatives Considered**:
  - System `ssh-keygen`: Fragile across platforms (especially Windows).

### Decision 4: Read-only workspace volume mount (`/workspace:ro`) and remote venv installation

Mount host workspace as `/workspace:ro` and execute `pip install /workspace` in the container's `/home/ubuntu/venv`.

- **Rationale**: Read-only mount prevents host file mutation while providing instant access. Installing into the remote virtualenv copies `aiida_pythonjob_ins` so that by-reference function cloudpickling succeeds.
- **Alternatives Considered**:
  - Copying source via SFTP/tar: Slower than volume mounting.

### Decision 5: Unconditional container cleanup and 30-second readiness timeout

Run container `stop` and `rm` in a `try...finally` fixture block. Poll `sinfo` every 0.5s up to a 30s timeout during setup.

- **Rationale**: Remote PythonJob execution leaves little state worth inspecting. Unconditional teardown prevents dangling containers. A 0.5s polling loop with 30s timeout keeps test execution fast while absorbing container cold-start delay.

### Decision 6: Register `@pytest.mark.containerized` and run in main CI step

Register the marker in `pyproject.toml` and execute containerized tests as part of the standard `pytest` run.

- **Rationale**: Deselection via `pytest -m "not containerized"` provides an easy opt-out for developers without container runtimes. GitHub Actions runners (`ubuntu-latest`) have Docker pre-installed, allowing automatic integration test execution in CI.

## Risks / Trade-offs

- **[Risk] Container cold-start / image download delay on first run** → *Mitigation*: Docker layers are cached in CI and local dev after initial pull; 30s setup timeout handles cold starts.
- **[Risk] Local port collision** → *Mitigation*: Map SSH port via `-p 127.0.0.1::22` to let the container engine allocate a free ephemeral port dynamically.
