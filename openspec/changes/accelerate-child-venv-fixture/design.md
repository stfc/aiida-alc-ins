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

## Benchmarks (task 2.3)

Measured via `pytest -m venv_code --durations=0`, reporting the `setup` phase
of `test_dispersion_pythonjob_matches_direct_call[aiida_free_python_code]`
(the `venv_child_environment` fixture build/install/uninstall/verify cost),
on the same machine and project checkout:

| Tool | Run                                    | Setup time |
|------|-----------------------------------------|-----------|
| `uv` | cold (`uv cache clean` beforehand)      | 3.17s     |
| `uv` | pre-cached (immediate re-run)           | 3.12s     |
| `pip`| cold (`~/.cache/pip` removed beforehand)| 27.75s    |
| `pip`| pre-cached (immediate re-run)           | 27.50s    |

Both code paths pass `--no-cache`/`--no-cache-dir` to their respective tool
(per Decision 1), so neither reuses a package cache between runs; the
cold/pre-cached figures are consistent for each tool because that flag makes
every run effectively "cold" from the package manager's own cache
perspective. The ~9x speedup comes from `uv`'s resolver and installer being
faster than pip's even without its cache, not from cache reuse. This confirms
the ~30s-per-matrix-leg saving from the proposal.
