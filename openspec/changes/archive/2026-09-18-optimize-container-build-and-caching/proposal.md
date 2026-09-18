# Optimize container build layering and CI caching

## Why

In `tests/container/Dockerfile`, source code (`src/`) is copied into the build context alongside package metadata before third-party dependencies are installed. Consequently, any code edit in `src/` busts Docker's layer cache for the entire dependency layer (500MB of packages including NumPy, SciPy, Euphonic, and AbINSLib). In continuous integration, this forces a cold re-download of all dependencies on every pull request commit, adding ~50–60 seconds to container-building.

Splitting third-party dependency installation from the package source copy allows heavy dependencies to remain cached across ordinary code commits. Pairing this layer separation with GitHub Actions Docker cache integration allows workflow runs to reuse base layers across runs rather than building from scratch.

## What Changes

- Refactor `tests/container/Dockerfile` into distinct caching stages:
  - Base OS, OpenSSH server, and HyperQueue installation (rarely changes).
  - Pre-installation of third-party runtime dependencies from `pyproject.toml` and `wheels/` into `/home/ubuntu/venv` using `uv pip install -r pyproject.toml` (cached across code edits in both Podman/Buildah and Docker).
  - Package source (`src/`) copied and installed with `uv pip install --no-deps .`, followed by `aiida-core` / `aiida-pythonjob` removal and purity verification.
- Support a `CONTAINER_ENGINE` environment variable in `tests/container_support.py:detect_container_engine()`, allowing explicit selection of `docker` or `podman` while retaining `("podman", "docker")` automatic detection by default.
- Update GitHub Actions workflow (`.github/workflows/ci.yml`) to set `CONTAINER_ENGINE: docker` and leverage official Docker Buildx actions with native layer caching (`type=gha`) across workflow runs, also verifying Docker engine compatibility in CI.

## Capabilities

### New Capabilities

*(None)*

### Modified Capabilities

*(None - behavioral requirements in `testing-and-ci` are unchanged; `skip_specs: true` is set)*

## Non-goals

- Altering the remote execution environment contract (it remains AiiDA-free with HyperQueue).
- Publishing pre-built container images to an external registry like GHCR.
- Removing Podman support (local development continues to default to and prefer Podman).

## Impact

- `tests/container/Dockerfile`: Layer order and install steps.
- `tests/container_support.py`: Support `CONTAINER_ENGINE` environment variable in `detect_container_engine()`.
- `.github/workflows/ci.yml`: Docker Buildx caching configuration and `CONTAINER_ENGINE: docker`.
- Speeds up local container rebuilds during development from ~50s to ~2s when only `src/` changes (under both Podman and Docker).
- Significantly reduces CI container build time and bandwidth usage.
