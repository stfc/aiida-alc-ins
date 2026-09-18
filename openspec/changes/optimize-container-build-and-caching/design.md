# Design: Optimize container build layering and CI caching

## Context

The integration test container (`tests/container/Dockerfile`) provisions an ephemeral SSH + HyperQueue environment with an AiiDA-free Python 3.12 virtualenv.

Currently, step 6 copies `pyproject.toml`, `wheels`, and `src` together:
```dockerfile
COPY pyproject.toml README.md LICENSE /tmp/deps/
COPY wheels /tmp/deps/wheels
COPY src /tmp/deps/src
RUN su - ubuntu -c "uv venv ... && uv pip install --no-cache ... ."
```
Because `src/` changes with each commit, the `RUN` step always invalidates cache.

## Decisions

### Decision 1: Two-stage dependency and source installation
1. Stage dependencies:
   - Copy `pyproject.toml` and vendored wheels to `/tmp/deps/`.
   - Install third-party dependencies into the venv (e.g. via `uv pip install` of dependencies or compiling from `pyproject.toml`).
2. Stage source:
   - Copy `src/` to `/tmp/deps/src`.
   - Install our package with `--no-deps`.
   - Uninstall `aiida-core` and `aiida-pythonjob`.
   - Verify purity (`assert "aiida" not in sys.modules`).

This ensures edits to `src/` only re-run the final `--no-deps` install (~0.5s).

### Decision 2: CI Docker layer caching
- In GitHub Actions (`.github/workflows/ci.yml`), use `actions/cache` or Buildx cache (`cache-from` / `cache-to`) to persist Docker layers across workflow runs keyed on `tests/container/**` and `pyproject.toml`.
