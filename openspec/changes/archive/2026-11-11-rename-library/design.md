# Design: Rename Library and Entry Points

## Context

See `proposal.md` for motivation. The distribution was published to PyPI as `aiida-alc-ins` in version 0.1.0. The code in `src/aiida_pythonjob_ins` and entry points with prefix `pythonjob_ins.*` were retained for that release.

The project uses `uv_build` as its build backend, Ruff with `TID252` (banning relative imports across package boundaries, requiring absolute imports), Sphinx with `sphinx-autoapi` pointed at `src/aiida_pythonjob_ins`, and standard AiiDA plugin factories (`WorkflowFactory`, `DataFactory`).

## Goals / Non-Goals

**Goals:**
- Move `src/aiida_pythonjob_ins/` to `src/aiida_alc_ins/`.
- Update all intra-package and test imports to `aiida_alc_ins`.
- Update the library logger namespace to `aiida_alc_ins`.
- Update `pyproject.toml` entry points under `aiida.data` and `aiida.workflows` to prefix `alc_ins.*`.
- Update all tests, fixtures, and documentation to use `alc_ins.*` entry points and `aiida_alc_ins` imports.
- Ensure the test suite, linting (`ruff check`, `ruff format`), and Sphinx docs build cleanly.

**Non-Goals:**
- Retain deprecated alias modules (e.g. `aiida_pythonjob_ins` redirecting to `aiida_alc_ins`) or dual entry points.
- Rename the PyPI distribution (`aiida-alc-ins` is already correct).
- Alter any calculation, workflow logic, or data schemas.

## Decisions

### Decision: Clean break migration without backward-compatibility shims

- **Chosen**: Immediate hard break. Version 0.2.0 will only provide `aiida_alc_ins` and register `alc_ins.*` entry points.
- **Alternatives considered**: Providing a dummy `aiida_pythonjob_ins` package that issues `FutureWarning` / `DeprecationWarning` and re-exports symbols, and registering duplicate entry points under both prefixes.
- **Rationale**: The 0.1.0 release notes explicitly documented that 0.1.0 was the only PyPI release using `aiida_pythonjob_ins` and that 0.2.0 would introduce the rename. Maintaining dual registration would complicate AiiDA process provenance (which records plugin entry-point names in node attributes) and leave legacy debt in a pre-1.0 prototype.

### Decision: Entry point prefix `alc_ins`

- **Chosen**: Prefix `alc_ins` for all entry points (e.g. `alc_ins.dispersion`, `alc_ins.force_constants`).
- **Alternatives considered**:
  - `alc-ins` (hyphenated): Permitted by setuptools/packaging, but deviates from the dominant community pattern.
  - `pythonjob_ins`: The legacy name being phased out.
- **Rationale**: AiiDA's Plugin System Specification defines the entry-point convention as `<plugin_name>.<ep_name>` where `<plugin_name>` matches the module name minus `aiida_`. In the official `aiidateam/aiida-registry`, multi-word plugins uniformly use underscores (e.g. `bands_inspect`, `wannier90_workflows`, `crystal_dft`).

### Decision: `uv_build` package directory layout

- **Chosen**: Standard `src/aiida_alc_ins` directory.
- **Rationale**: `uv_build` automatically infers the top-level Python package from the project name by converting hyphens to underscores (`aiida-alc-ins` $\to$ `aiida_alc_ins`). In 0.1.0, `pyproject.toml` or `uv_build` had to accommodate the mismatch; with `src/aiida_alc_ins`, the directory layout directly matches standard wheel building conventions without special overrides.

## Risks / Trade-offs

- **[Risk] Stale virtual environment still containing old package artifacts**  
  $\to$ **Mitigation**: `uv run` resynchronizes the editable install. Running `uv sync --reinstall-package aiida-alc-ins` or `uv run pytest tests/test_version.py` validates that `version("aiida-alc-ins")` and `import aiida_alc_ins` resolve from the updated source tree.
- **[Risk] Lingering references to `pythonjob_ins` in tests or documentation snippets**  
  $\to$ **Mitigation**: `tests/test_entry_points.py` inspects all registered entry points and confirms they load. A repository-wide text search (`rg "pythonjob_ins"`) will verify no unintended occurrences remain outside of historical changelogs and archived specs.
- **[Risk] Sphinx autoapi configuration pointing to old source path**  
  $\to$ **Mitigation**: Update `autoapi_dirs = ["../../src/aiida_alc_ins"]` in `docs/source/conf.py` and test the docs build (`make -C docs html`).

## Migration Plan

1. Rename directory `src/aiida_pythonjob_ins` to `src/aiida_alc_ins`.
2. Update `src/aiida_alc_ins/` internal imports and logger (`logging.getLogger("aiida_alc_ins")`).
3. Update `pyproject.toml` entry point definitions to `alc_ins.*` pointing to `aiida_alc_ins.*`.
4. Update `tests/`: replace imports of `aiida_pythonjob_ins` with `aiida_alc_ins`, and entry point strings `pythonjob_ins.*` with `alc_ins.*`.
5. Update `docs/`: update `conf.py` autoapi paths, tutorials, and `README.md`.
6. Run `ruff check`, `ruff format`, `pytest`, and `sphinx-build` to verify full alignment.
