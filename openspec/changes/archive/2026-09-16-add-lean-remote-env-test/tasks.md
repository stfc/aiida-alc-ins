## 1. Marker registration

- [x] 1.1 Register the `venv_code` marker in `pyproject.toml` and verify `pytest --markers` lists it

## 2. Session-scoped child environment fixture

- [x] 2.1 Create a `venv.EnvBuilder` subclass in `tests/conftest.py` whose `post_setup` hook captures `context.env_exe` and verify the class is present and importable
- [x] 2.2 Add helper to read `[tool.uv] find-links` from `pyproject.toml` using `tomllib` and verify it returns the expected path on aarch64
- [x] 2.3 Implement `venv_child_environment` session fixture: create venv under `tmp_path_factory`, install project non-editable with `--find-links` if present, and verify the fixture creates a directory containing `pyvenv.cfg`
- [x] 2.4 Extend fixture to uninstall `aiida-core` and `aiida-pythonjob` via subprocess and verify `pip list` output in the child no longer contains them
- [x] 2.5 Add assertion that `import aiida` and `import aiida_pythonjob` both fail in the child interpreter, and verify the assertion runs during fixture setup
- [x] 2.6 Add skip condition when `ensurepip` is unavailable and verify the skip message appears when running with `PYTHONDONTWRITEBYTECODE=1` unset on a system without `ensurepip`

## 3. Remote code fixture

- [x] 3.1 Create `remote_python_code` fixture marked `venv_code` that uses `aiida_code_installed` with `filepath_executable` set to the child interpreter and verify `pytest --collect-only -m venv_code` shows it

## 4. Test implementation

- [x] 4.1 Parametrize `test_dispersion_pythonjob_matches_direct_call` to accept both `python_code` and `remote_python_code` and verify the test runs twice (once per code) when collected under `-m venv_code`
- [x] 4.2 Add `test_child_environment_lacks_aiida` marked `venv_code` that asserts the child interpreter cannot import `aiida` or `aiida_pythonjob`, and verify it passes

## 5. Verification

- [x] 5.1 Run `uv run pytest -m "not containerized and not venv_code"` and verify all non-venv_code tests pass
- [x] 5.2 Run `uv run pytest -m venv_code` and verify the venv_code tests pass
- [x] 5.3 Run `uv run pytest -m "not containerized"` (default selection) and verify both groups pass together
