# Tasks

## 1. Package Structure and Core Imports

- [ ] 1.1 Move directory `src/aiida_pythonjob_ins` to `src/aiida_alc_ins` and verify expected files are present under the new path
- [ ] 1.2 Update intra-package absolute imports and logger namespace to `aiida_alc_ins` across all files in `src/aiida_alc_ins/`, and verify the package imports cleanly via `uv run python -c "import aiida_alc_ins; print(aiida_alc_ins.__version__)"`

## 2. Packaging and Entry Point Declarations

- [ ] 2.1 Update `pyproject.toml` entry points under `aiida.data` and `aiida.workflows` to prefix `alc_ins.*` pointing to `aiida_alc_ins.*` targets
- [ ] 2.2 Update `tests/test_version.py` and `tests/test_entry_points.py` to import `aiida_alc_ins` and assert `alc_ins.*` entry points, and verify completion by running `uv run pytest tests/test_version.py tests/test_entry_points.py`

## 3. Test Suite Migration

- [ ] 3.1 Update all remaining test files across `tests/` to import from `aiida_alc_ins` and request `alc_ins.*` entry points from AiiDA factories
- [ ] 3.2 Run the full test suite with `uv run pytest` and verify all tests pass

## 4. Documentation and Cleanups

- [ ] 4.1 Update `docs/source/conf.py` autoapi paths and tutorial gallery scripts in `docs/source/tutorials/` to import `aiida_alc_ins` and use `alc_ins.*`, and verify docs build cleanly with `uv run --group doc sphinx-build -b html docs/source docs/build/html`
- [ ] 4.2 Update `README.md` quick example to load `alc_ins.tosca_from_force_constants`
- [ ] 4.3 Run `uv run ruff check .` and `uv run ruff format --check .` to verify code quality and formatting across all modified files

## Workflow follow-up

- Archive the change after implementation and review.
- Update main specs (`openspec/specs/plugin-packaging/spec.md`).
