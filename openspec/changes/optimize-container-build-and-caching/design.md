# Design: Optimize container build layering and CI caching

## Context

Integration tests (`tests/test_remote_ssh.py` and workflow container tests) execute against an ephemeral container managed by `tests/container_support.py` (`SSHContainer`). The container runs Ubuntu 22.04 with OpenSSH, an unprivileged HyperQueue worker, and an AiiDA-free Python 3.12 virtual environment containing the package's pure-Python operations and scientific dependencies (Euphonic, NumPy, SciPy, Seekpath, AbINSLib).

Currently, `tests/container/Dockerfile` copies the entire repository context (`pyproject.toml`, `wheels/`, and `src/`) into `/tmp/deps/` in a single step before executing `uv pip install --python /home/ubuntu/venv .`. Because `src/` changes with virtually every commit, Docker's and Buildah's layer cache is invalidated at the `COPY` instruction, forcing a full re-resolution and cold download/install of ~500MB of third-party dependencies during every build.

In `tests/container_support.py`, `detect_container_engine()` detects container runtimes by checking `("podman", "docker")` in sequence. On GitHub-hosted `ubuntu-latest` runners, both Podman and Docker are pre-installed. Consequently, tests currently select Podman by default. In CI, across four matrix legs (`python-version: ["3.11", "3.12", "3.13", "3.14"]`), each runner VM starts with empty storage, causing all four jobs to execute a cold 50-second container build from scratch on every run.

See `proposal.md` for motivation and scope.

## Goals / Non-Goals

**Goals:**
- Separate external dependency installation from local source installation in `tests/container/Dockerfile` so that routine edits to `src/` take <2 seconds to rebuild locally under both Podman and Docker.
- Support a `CONTAINER_ENGINE` environment variable in `tests/container_support.py:detect_container_engine()`, allowing explicit selection of `docker` or `podman` while retaining `("podman", "docker")` auto-detection as the default.
- Set `CONTAINER_ENGINE: docker` in GitHub Actions CI to leverage official Docker actions (`docker/setup-buildx-action`, `docker/build-push-action`) and GitHub's native cache service (`type=gha`), eliminating redundant container rebuilds between runs.
- Provide continuous assurance in CI that the test container setup functions reliably under Docker, complementing local developer verification under Podman.
- Prevent parallel matrix jobs from thrashing GitHub's cache storage by scoping cache exports to a single canonical runner.

**Non-Goals:**
- Publishing pre-built container images to GitHub Container Registry (GHCR) or Docker Hub (avoids registry authentication, credential management, and external retention policies).
- Forcing Docker locally on developer machines: local development continues to default to and prefer Podman, benefiting from local Buildah layer caching.
- Custom caching scripts or tarball artifact management.

## Decisions

### Decision 1: Two-stage dependency and source installation in Dockerfile
Refactor `tests/container/Dockerfile` to isolate third-party dependencies from package source code:

1. **System & Environment Preparation**:
   - Provision Ubuntu system packages (OpenSSH, curl, ca-certificates).
   - Install HyperQueue standalone binary and `uv`.
   - Create `ubuntu` user, create `/tmp/aiida_run`, configure SSH keys and daemon.
   - Initialize `/home/ubuntu/venv` using `uv venv --no-cache --python 3.12`.

2. **Stage 1 — Dependencies (Heavily Cached)**:
   - Copy only dependency manifests: `pyproject.toml` and `wheels/` to `/tmp/deps/`.
   - Install third-party requirements directly into the venv via:
     ```dockerfile
     RUN cd /tmp/deps && su - ubuntu -c "uv pip install --no-cache --python /home/ubuntu/venv -r pyproject.toml"
     ```
   - When only `src/` changes, Docker and Buildah detect that `pyproject.toml` and `wheels/` have unchanged checksums, making this layer an instant cache hit.

3. **Stage 2 — Source Installation & Environment Sanitization**:
   - Copy `src/` to `/tmp/deps/src`.
   - Install `aiida-pythonjob-ins` without reinstalling dependencies using `--no-deps`:
     ```dockerfile
     RUN cd /tmp/deps && su - ubuntu -c "\
         uv pip install --no-cache --python /home/ubuntu/venv --no-deps . && \
         uv pip uninstall --python /home/ubuntu/venv aiida-core aiida-pythonjob && \
         /home/ubuntu/venv/bin/python -c 'import aiida_pythonjob_ins.operations; import sys; assert \"aiida\" not in sys.modules'"
     ```
   - Execution time for this layer is <1 second because all compiled C-extensions (NumPy, SciPy, Euphonic) were already installed in Stage 1.

*Alternatives considered:*
- *Single-stage build (current state)*: Rejected. Any line change in `src/` invalidates cache and triggers 50s of package downloads.
- *Multi-stage build discarding build tools*: Rejected. The test container is ephemeral and destroyed after the test run; shrinking image footprint by stripping build tools adds complexity with negligible test performance benefit.

---

### Decision 2: Environment variable override for container engine selection
Update `detect_container_engine()` in `tests/container_support.py` to allow explicit engine selection:

```python
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
```

- **Local Development**: Continues to default to `podman` on systems where it is available.
- **CI Workflows**: Can explicitly pass `CONTAINER_ENGINE: docker` to target Docker and its native Buildx caching infrastructure.
- **Dual-Engine Validation**: Gives developers and CI the flexibility to verify both engines on demand (`CONTAINER_ENGINE=docker pytest` or `CONTAINER_ENGINE=podman pytest`).

---

### Decision 3: CI layer caching via official Docker Buildx actions and GHA cache backend
In `.github/workflows/ci.yml`, run tests with `CONTAINER_ENGINE: docker` and use official Docker actions with BuildKit's built-in GitHub Actions Cache backend (`type=gha`):

```yaml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v3

- name: Build and cache test container
  uses: docker/build-push-action@v6
  with:
    context: .
    file: tests/container/Dockerfile
    tags: aiida-ssh-hq-test:latest
    load: true
    cache-from: type=gha,scope=container-test
    cache-to: ${{ matrix.python-version == '3.12' && 'type=gha,mode=max,scope=container-test' || '' }}
```

And in the test step:
```yaml
- name: Run tests
  env:
    CONTAINER_ENGINE: docker
  run: uv run pytest -v
```

**Why Docker in CI over Podman/Buildah:**
1. **First-party GHA Cache Exporter**: Docker BuildKit includes a native GitHub Actions Cache exporter (`type=gha`). It communicates directly with the GitHub Actions cache service via `$ACTIONS_RESULTS_URL` without external authentication or registry setups.
2. **Buildah Lacks GHA Cache API Support**: Upstream Buildah/Podman only supports `--cache-from` and `--cache-to` pointing to an external OCI registry (such as Quay.io or GHCR). Setting up GHCR caching requires `permissions: packages: write`, registry authentication, and image retention policies.
3. **`podman save / load` Does Not Provide Layer Cache**: Empirical tests confirm that loading an exported image tarball via `podman load` populates the image tag but strips Buildah's intermediate build-cache graph metadata. Subsequent `podman build` runs rebuild all instructions from scratch.
4. **Caching Container Storage is Unsafe**: Caching Podman's rootless storage (`~/.local/share/containers/storage`) with `actions/cache` is explicitly warned against by Buildah maintainers because overlayfs driver metadata, hardlinks, and subuid mappings break across fresh runner VMs.
5. **Bonus Engine Assurance**: Running Docker in CI ensures both Podman (used during local development) and Docker (used in CI) are exercised regularly, ensuring cross-runtime compatibility.

---

### Decision 4: Cache scoping and matrix coordination
The CI workflow runs tests across a matrix of Python versions (`3.11`, `3.12`, `3.13`, `3.14`). The test container itself always runs an internal Python 3.12 environment, independent of the matrix host version.

To optimize matrix execution:
- All matrix jobs read from the shared cache (`cache-from: type=gha,scope=container-test`).
- Only the canonical Python 3.12 matrix runner writes back to the cache (`cache-to: ${{ matrix.python-version == '3.12' && 'type=gha,mode=max,scope=container-test' || '' }}`).
- Scoping with `scope=container-test` ensures the container build cache does not collide with any other potential workflow caches in the repository.
- `load: true` ensures the built image is injected into the runner's Docker daemon. When `pytest` executes `ensure_container_image()`, the image already exists in the daemon, completing in ~0.5 seconds.

---

## Risks / Trade-offs

- **[Risk] Docker service unavailable or disabled on CI runner** →
  **Mitigation:** GitHub-hosted `ubuntu-latest` environments provide the Docker daemon running by default. `detect_container_engine()` verifies `engine info` exits with code 0 before accepting it.
- **[Risk] GitHub Actions cache eviction (10GB repo quota or 7-day inactivity)** →
  **Mitigation:** `type=gha` handles cache misses gracefully. If evicted, the build falls back to a clean build from source. Thanks to the two-stage Dockerfile layering, the base layers rebuild reliably without failing.
- **[Risk] Read-only cache permissions on certain pull request triggers** →
  **Mitigation:** Under standard `pull_request` triggers against the repository, GitHub grants read-write cache access. For untrusted forks where write access is denied by GitHub security policies, `cache-from` still reads from `main`, while write failures can be made non-fatal with `ignore-error=true` in `cache-to` (e.g., `type=gha,mode=max,scope=container-test,ignore-error=true`).
- **[Risk] Discrepancy between Podman (local) and Docker (CI)** →
  **Mitigation:** Both engines use standard OCI specifications and parse identical Dockerfiles. The container runs an identical unprivileged SSH + HyperQueue environment with standard loopback port mapping (`127.0.0.1::22`). Having CI use Docker while local development uses Podman actively verifies that the plugin works across both major container runtimes.
