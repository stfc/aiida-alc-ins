# Design: Accelerate child venv fixture with optional uv support

## Context

The test suite exercises PythonJob execution in an environment where AiiDA is not installed. To do this, `conftest.py` implements `AiiDAFreeEnvBuilder(venv.EnvBuilder)` which creates an ephemeral venv, installs the project non-editable, and uninstalls `aiida-core` and `aiida-pythonjob`.

Currently, this installation runs `python -m pip install --no-cache-dir .`, which resolves and builds packages via standard pip, taking ~30–40s on every run.

## Decisions

### Decision 1: Progressive enhancement via `shutil.which("uv")`
- Probe PATH for `uv` using standard library `shutil.which("uv")`.
- If `uv` is found:
  - Run `uv pip install --python <child_python> --no-cache <project_root>` (and `--find-links` if present).
  - Run `uv pip uninstall --python <child_python> aiida-core aiida-pythonjob`.
- If `uv` is not found:
  - Fall back to the existing `[str(child_python), "-m", "pip", "install", ...]` commands.

### Decision 2: Maintain strict isolation and verification
- Continue verifying that `aiida` and `aiida_pythonjob` cannot be imported in the child environment before yielding `child_python`.
- Continue verifying `pyvenv.cfg` presence.
