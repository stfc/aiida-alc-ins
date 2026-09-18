# Accelerate child venv fixture with optional uv support

## Why

The `venv_child_environment` test fixture in `tests/conftest.py` creates an ephemeral virtual environment and runs `pip install --no-cache-dir .` to test execution in an AiiDA-free interpreter. On every matrix leg in CI and during local testing, standard `pip` takes 30–40 seconds resolving and installing dependencies from PyPI.

`uv` can perform the same installation in under a second. However, requiring `uv` as a hard prerequisite for running the test suite would impose an opinionated tool on contributors who use standard `pip`, `venv`, `conda`, or `pixi`. By using `uv` conditionally when present on PATH while falling back cleanly to standard `pip`, the fixture can run orders of magnitude faster in CI and for `uv` users without breaking tool neutrality.

## What Changes

- Update `conftest.py:AiiDAFreeEnvBuilder` to detect if `uv` is available on PATH (`shutil.which("uv")`).
- When `uv` is available, invoke `uv pip install --python <child_python>` to populate the child virtual environment from the project directory.
- When `uv` is absent, fall back to standard `python -m pip install`.
- Apply the same detection logic to uninstallation of `aiida-core` and `aiida-pythonjob` (`uv pip uninstall` vs `pip uninstall`).

## Capabilities

### New Capabilities

*(None)*

### Modified Capabilities

*(None - behavioral requirements in `testing-and-ci` are unchanged; `skip_specs: true` is set)*

## Non-goals

- Making `uv` a required dependency for running pytest locally.
- Modifying the container integration test fixture (covered in separate container changes).
- Changing which tests use the `venv_code` marker.

## Impact

- `tests/conftest.py`: `AiiDAFreeEnvBuilder` post-setup install commands.
- Saves ~30 seconds per matrix leg in CI and for local developer test runs.
