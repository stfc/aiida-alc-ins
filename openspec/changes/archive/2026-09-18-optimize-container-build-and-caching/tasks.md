# Tasks

## 1. Containerfile Layer Optimization

- [x] 1.1 Refactor `tests/container/Dockerfile` to isolate third-party dependencies (`pyproject.toml` and `wheels/`) from `src/`, installing dependencies via `uv sync --no-install-project` in Stage 1 and package source with `--no-deps` in Stage 2.
- [x] 1.2 Verify local container build completes cleanly and satisfies the remote AiiDA-free purity check (`assert "aiida" not in sys.modules`).
- [x] 1.3 Benchmark local rebuild time on a simulated `src/` edit and verify that Stage 1 dependencies are cached, finishing the rebuild in <2 seconds.

## 2. Container Engine Selection & CI Caching

- [x] 2.1 Update `detect_container_engine()` in `tests/container_support.py` to support `CONTAINER_ENGINE` environment variable override while preserving automatic detection order `("podman", "docker")` when unset.
- [x] 2.2 Update `.github/workflows/ci.yml` to set up Docker Buildx (`docker/setup-buildx-action@v3`), cache container layers via BuildKit GHA backend (`docker/build-push-action@v6`), and set `CONTAINER_ENGINE: docker` in the test step.

## 3. Quality & Regression Verification

- [x] 3.1 Run `uv run ruff check` and `uv run ruff format --check` across `src/` and `tests/` to verify code quality compliance.
- [x] 3.2 Run the fast test suite (`uv run pytest -m "not containerized"`) to verify no regressions in local testing workflows.
