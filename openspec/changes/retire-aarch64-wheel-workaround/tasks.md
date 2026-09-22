# Tasks

## 1. Project Configuration & Directory Cleanup

- [x] 1.1 Remove `[tool.uv] find-links = ["wheels"]` and associated wheel workaround comments from `pyproject.toml`.
- [x] 1.2 Remove `wheels/` directory and `wheels/.gitkeep`.
- [x] 1.3 Remove `wheels/*.whl` and the introductory comment from `.gitignore`.

## 2. Test Environment & Containerfile Streamlining

- [x] 2.1 Remove `COPY wheels /tmp/deps/wheels` from `tests/container/Dockerfile`.
- [x] 2.2 In `tests/conftest.py`, remove `get_find_links_from_pyproject()` and clean up the `find_links` parameter plumbing from `AiiDAFreeEnvBuilder`.

## 3. Documentation & Context Updates

- [x] 3.1 Remove the `### aarch64 Euphonic wheel (local workaround)` section from `README.md`.
- [x] 3.2 Update `openspec/config.yaml` to remove references to local wheel staging and aarch64 Euphonic wheel constraints.

## 4. Verification

- [x] 4.1 Run `uv sync` to confirm standard package resolution and virtual environment synchronization without `find-links`.
- [x] 4.2 Run `uv run ruff check` and `uv run ruff format --check` across `src/` and `tests/`.
- [x] 4.3 Run `uv run pytest -m "not containerized"` to verify the test suite passes cleanly.
