## Context

The current integration test setup (`tests/container/Dockerfile`, `tests/slurm_support.py`, `tests/test_remote_slurm.py`) couples an SSH daemon, Slurm controller (`slurmctld`), Slurm compute daemon (`slurmd`), munge authentication, and an editable project mount into a single heavy container image. The container image carries committed private keys (`tests/container/id_rsa`), brittle multi-daemon startup sequences in `entrypoint.sh`, and hardcoded local port probing.

Furthermore, `tests/conftest.py` currently runs integration tests in a single-process execution model. As explored in `openspec/changes/archive/2026-08-26-remove-pytest-xdist/proposal.md`, running `pytest-xdist` with session-scoped container fixtures without coordination causes each worker process to spawn its own container, causing build races, port collisions, and excessive resource consumption.

See `proposal.md` for motivation on decoupling the container from Slurm, introducing HyperQueue, and enabling parallel test execution.

## Goals / Non-Goals

**Goals:**
- Replace the Slurm container with a minimal, auditable SSH + HyperQueue container.
- Use `aiida-hyperqueue` as the primary scheduler to provide realistic asynchronous job lifecycle testing (submit, queue, poll, retrieve).
- Provide xdist-safe lazy container initialization using the official `pytest-xdist` `FileLock` pattern.
- Ensure unit tests execute immediately at $t=0$ without waiting for container bring-up via test collection sorting (`pytest_collection_modifyitems`).
- Eliminate committed private keys from version control by generating dynamic session SSH keys via `aiida-core`'s `ssh_key` fixture.
- Delegate port binding to the container runtime to avoid host port races.
- Test remote execution against a clean, AiiDA-free Python environment.

**Non-Goals:**
- Retain Slurm in automated CI testing (Slurm moves to a human-run tutorial in `document-ssh-pythonjob-computers`).
- Support nested container execution inside restricted rootless sandboxes (handled locally by `pytest -m venv_code`).
- Introduce cross-container distributed HyperQueue clusters (a single-node HQ server and worker within the container is sufficient).

## Decisions

### Decision 1: HyperQueue as the containerized scheduler

- **Approach**: The container runs an unprivileged HyperQueue server (`hq server start &`) and worker (`hq worker start &`). An AiiDA `Computer` is configured with `transport_type="core.ssh"` and `scheduler_type="hyperqueue"` using the `aiida-hyperqueue` plugin.
- **Rationale**: HyperQueue provides a modern, lightweight scheduler implemented as a single static Rust binary (`hq`). It runs entirely in user space without root, munge keys, or system services. Unlike `core.direct` (which merely launches background processes with `nohup` and lacks queuing states or core allocation), HyperQueue provides a realistic asynchronous job lifecycle (`QUEUED` → `RUNNING` → `FINISHED`) and native JSON CLI output (`hq submit --json`).
- **No Direct Fallback Machinery**: We commit to HyperQueue directly. We do not implement fallback abstraction layers, dynamic toggles, or configuration branches for `core.direct`. If HyperQueue were to fail fundamentally, reverting to `core.direct` would simply be an edit to the fixture string, but no code is added to facilitate dual schedulers.
- **Worker Concurrency**: The containerized `hq worker` detects available host cores via `nproc` by default, maximizing local test throughput. An optional environment variable (`HQ_CPUS`) may override this if a developer wishes to cap test CPU usage during active workstation use.
- **Alternatives considered**:
  - *Keep Slurm (`core.slurm`)*: Rejected due to high maintenance overhead (munge auth, multi-daemon startup races, node state management, ~824MB+ image).
  - *Use `core.direct`*: Rejected because it cannot queue jobs, has no worker slot limits, and does not test an asynchronous scheduler lifecycle.

### Decision 2: Multi-process coordination via lazy `FileLock` and test collection ordering

- **Approach**: Adopt the canonical `pytest-xdist` shared session fixture recipe using `filelock.FileLock` in `tmp_path_factory.getbasetemp().parent / "container.lock"`. In `tests/conftest.py`, implement `pytest_collection_modifyitems` to sort tests so that `containerized` tests execute after all non-containerized unit tests. Teardown is coordinated on the controller process in `pytest_sessionfinish`.
- **Rationale**: In `pytest-xdist`, each worker process initializes session fixtures independently unless synchronized. Test ordering ensures all 70+ unit tests run in parallel at $t=0$ without any container startup lag. The first worker to encounter a containerized test acquires the `FileLock`, starts the container, and writes connection details (`container_info.json`). Subsequent workers acquire the lock, read the existing connection details, and connect to the shared container.
- **Alternatives considered**:
  - *Eager controller hook (`workerinput`)*: Starts the container before workers are spawned. Rejected because it delays unit tests by 5–8 seconds even when running fast unit test slices.
  - *Per-worker containers ("spawn more")*: Rejected due to concurrent build races on the same image tag and high CPU/memory consumption.
  - *Worker grouping (`@pytest.mark.xdist_group`)*: Confines all containerized tests to a single worker. While simple, it prevents running independent workflow tests in parallel across workers.

### Decision 3: Structured ephemeral SSH keypair (`SSHKeyPair`) via Paramiko and runtime port assignment

- **Approach**: Generate a dynamic SSH keypair during test session setup using Paramiko's high-level `RSAKey.generate(2048)` API. Instead of returning a bare private key path and writing a companion `.pub` file as a hidden side-effect, return an explicit `SSHKeyPair` dataclass containing typed paths to both `private_key` and `public_key`. Pass the keypair to `SSHContainer`, which volume-mounts `public_key` to `/home/ubuntu/.ssh/authorized_keys` and authenticates using `private_key`. Expose SSH on `127.0.0.1` using container runtime dynamic port mapping (`-p 127.0.0.1::22`), and query the assigned port with `inspect`.
- **Rationale**: 
  - Eliminates the low-level `cryptography.hazmat` package in favor of high-level primitives already provided by Paramiko (an existing project dependency).
  - Eliminates the confusing side-effect where `ssh_key` yielded a private key path while secretly writing a `.pub` file that consumers had to guess using `.with_suffix(".pub")`.
  - Removes the committed private key `tests/container/id_rsa` from git.
  - Runtime dynamic port assignment avoids port collision races between parallel test processes on loopback.
- **Alternatives considered**:
  - *`cryptography.hazmat` generation (upstream `aiida-core` pattern)*: Rejected due to unnecessary verbosity (30+ lines of low-level serialization code) and introducing hazardous primitives where high-level Paramiko APIs suffice.
  - *Bare private key `Path` with `.pub` side-effect file*: Rejected due to poor API clarity and hidden coupling.
  - *Pre-baked static keys in Dockerfile*: Security smell and causes static key reuse across all test sessions.
  - *Pre-probing free ports via `find_free_port()`*: Prone to race conditions under parallel execution where another process or worker binds the probed port before `docker run` can claim it.

### Decision 4: Clean, AiiDA-free remote Python virtualenv

- **Approach**: The container installs the package dependencies from `pyproject.toml` into a dedicated virtual environment (`/home/ubuntu/venv`) using `uv pip install --no-cache`, but explicitly omits `aiida-core` and `aiida-pythonjob`.
- **Rationale**: Validates the core architectural contract of `aiida-pythonjob`: job functions in `operations.py` are shipped by module reference and executed remotely in an interpreter where AiiDA is absent. An environment with AiiDA installed would mask illegal `import aiida` leaks.
- **Alternatives considered**:
  - *Installing full AiiDA on the container*: Defeats the test's purpose and inflates image size.
  - *Mounting host virtual environment*: Leaks host-specific paths, binaries, and editable links into the container.

### Decision 5: Base image selection: Ubuntu 22.04 minimal

- **Approach**: Build the container on `ubuntu:22.04` (minimal), installing `openssh-server`, `python3`, `ca-certificates`, and `curl`, then fetching the official standalone `hq` release binary from GitHub into `/usr/local/bin/hq`.
- **Rationale**: Ubuntu 22.04 uses `glibc`, ensuring complete compatibility with pre-built Python wheels for Euphonic and scientific dependencies across both x86_64 and aarch64.
- **Alternatives considered**:
  - *Alpine Linux*: Rejected because `musl` libc does not support standard `manylinux` wheels; scientific Python libraries (numpy, scipy) would require complex compilation from source.
  - *Debian 12 slim*: Viable, but Ubuntu 22.04 aligns with existing CI runners and tested base images.

## Risks / Trade-offs

- **[Risk: `aiida-hyperqueue` compatibility or behavior quirks with AiiDA 2.8]**  
  → *Mitigation*: The test computer is constructed explicitly in fixtures rather than using opaque helpers, making scheduler interactions auditable and issues straightforward to isolate.
- **[Risk: Container runtime unavailable in local development or sandboxes]**  
  → *Mitigation*: `detect_container_engine()` automatically skips `containerized` tests cleanly. Local developers and agents verify AiiDA-free remote execution using the fast in-process `pytest -m venv_code` suite.
- **[Risk: Orphan containers if a test run is killed abruptly (`SIGKILL`)]**  
  → *Mitigation*: Containers are assigned names with a unique prefix (`aiida-hq-test-<uuid>`). `pytest_sessionfinish` on the controller removes the container on normal completion or `SIGINT`/`SIGTERM`. A helper utility or subsequent test run can clean up stale prefixed containers.
- **[Risk: Worker contention for CPU inside the container]**  
  → *Mitigation*: `hq worker` detects host CPU count via `nproc` by default, but respects an optional `HQ_CPUS` environment variable override if specified.

## Open Questions

*(None. All architectural decisions, scheduler selection, worker allocation, and concurrency strategies are resolved.)*
