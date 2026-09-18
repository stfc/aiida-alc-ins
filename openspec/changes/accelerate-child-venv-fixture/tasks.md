# Tasks

## 1. Fixture Acceleration Implementation

- [x] 1.1 Add `uv` detection in `tests/conftest.py` via `shutil.which("uv")` and verify detection works in the environment.
- [x] 1.2 Update `venv_child_environment` fixture to use `uv pip install --python` and `uv pip uninstall --python` when `uv` is detected, while preserving the standard `python -m pip` fallback when `uv` is absent.

## 2. Verification and Benchmarking

- [x] 2.1 Execute `uv run pytest -m venv_code` and verify that the tests pass with the accelerated `uv` path.
- [x] 2.2 Verify that the fallback path works when `uv` is not present (or simulated absent), ensuring tool neutrality.
- [x] 2.3 Gather fixture setup timing benchmarks for cold and pre-cached starts using both `uv` and `pip` (via `pytest -m venv_code --durations=0`) and document the observed timings in `design.md`.
- [x] 2.4 Run full code quality checks with `uv run ruff check src/ tests/` and `uv run ruff format --check src/ tests/`.
