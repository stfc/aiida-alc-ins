## 1. Package Configuration

- [x] 1.1 Update `requires-python` to `>=3.10` and verify the package metadata is correct
- [x] 1.2 Add `target-version = "py310"` to `[tool.ruff]` and verify `ruff check` passes

## 2. Dependency Configuration

- [x] 2.1 Replace `abinslib==0.1.*` with Python-version-conditional sources and verify the file is syntactically valid
- [x] 2.2 Add `typing-extensions>=4.0.0` to dependencies and verify the file is syntactically valid

## 3. Source Code Updates

- [x] 3.1 Update `src/aiida_pythonjob_ins/data/base.py` to import `Self` from `typing_extensions` and verify the module imports successfully
- [x] 3.2 Update `src/aiida_pythonjob_ins/data/crystal.py` to import `Self` from `typing_extensions` and verify the module imports successfully
- [x] 3.3 Update `src/aiida_pythonjob_ins/data/force_constants.py` to import `Self` from `typing_extensions` and verify the module imports successfully

## 4. CI Configuration

- [x] 4.1 Update `.github/workflows/ci.yml` to include Python 3.10 in the test matrix and verify CI passes

## 5. Verification

- [x] 5.1 Run `uv pip compile pyproject.toml --python-version 3.10` and verify abinslib resolves from git source
- [x] 5.2 Run `uv pip compile pyproject.toml --python-version 3.11` and verify abinslib resolves from PyPI (version 0.1.*)
- [x] 5.3 Run `ruff check src/` and verify no linting errors
