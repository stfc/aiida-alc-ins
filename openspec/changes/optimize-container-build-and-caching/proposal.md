# Optimize container build layering and CI caching

## Why

In `tests/container/Dockerfile`, source code (`src/`) is copied into the build context alongside package metadata before third-party dependencies are installed. Consequently, any code edit in `src/` busts Docker's layer cache for the entire dependency layer (500MB of packages including NumPy, SciPy, Euphonic, and AbINSLib). In continuous integration, this forces a cold re-download of all dependencies on every pull request commit, adding ~50–60 seconds to container-building.

Splitting third-party dependency installation from the package source copy allows heavy dependencies to remain cached across ordinary code commits. Pairing this layer separation with GitHub Actions Docker cache integration allows workflow runs to reuse base layers across runs rather than building from scratch.

## What Changes

- Refactor `tests/container/Dockerfile` into distinct caching stages:
  1. Base OS, SSH server, and HyperQueue installation (rarely changes).
  2. Copy `pyproject.toml` and wheels, and pre-install third-party runtime dependencies into `/home/ubuntu/venv` (cached across code edits).
  3. Copy `src/` and install `aiida-pythonjob-ins` with `--no-deps`.
  4. Uninstall `aiida-core` and `aiida-pythonjob` to enforce the lean remote environment contract.
- Update GitHub Actions workflow (`.github/workflows/ci.yml`) to leverage Docker layer caching across workflow runs.

## Capabilities

### New Capabilities

*(None)*

### Modified Capabilities

*(None - behavioral requirements in `testing-and-ci` are unchanged; `skip_specs: true` is set)*

## Non-goals

- Altering the remote execution environment contract (it remains AiiDA-free with HyperQueue).
- Publishing pre-built container images to an external registry like GHCR.
- Replacing the container engine detection in `tests/container_support.py`.

## Impact

- `tests/container/Dockerfile`: Layer order and install steps.
- `.github/workflows/ci.yml`: Docker caching configuration.
- Speeds up local container rebuilds during development from ~25s to ~2s when only `src/` changes.
- Significantly reduces CI container build time and bandwidth usage.
