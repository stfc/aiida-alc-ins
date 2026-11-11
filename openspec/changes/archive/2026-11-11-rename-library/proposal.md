# Proposal: Rename Library and Entry Points for 0.2.0

## Why

The package distribution was renamed to `aiida-alc-ins` in version 0.1.0, but the Python import package retained the legacy prototype name `aiida_pythonjob_ins` and entry-point prefix `pythonjob_ins.*`. Aligning the import name to `aiida_alc_ins` and entry points to `alc_ins.*` resolves this discrepancy and delivers the planned 0.2.0 breaking change, establishing consistent naming across PyPI, Python imports, and AiiDA factories.

## What Changes

- **BREAKING**: Rename the import package from `aiida_pythonjob_ins` to `aiida_alc_ins`. All internal modules, imports, and logger namespaces (`aiida_alc_ins`) reflect the new name.
- **BREAKING**: Rename all registered AiiDA entry points under `aiida.data` and `aiida.workflows` from prefix `pythonjob_ins.*` to `alc_ins.*`:
  - `aiida.data`: `alc_ins.crystal`, `alc_ins.force_constants`, `alc_ins.qpoint_phonon_modes`
  - `aiida.workflows`: `alc_ins.force_constants`, `alc_ins.dispersion`, `alc_ins.dos`, `alc_ins.tosca_from_modes`, `alc_ins.tosca_from_force_constants`
- Update `pyproject.toml` entry points, package metadata, and `uv_build` package directory discovery.
- Update Sphinx documentation (`conf.py`, autoapi, tutorials) and the README to import `aiida_alc_ins` and load `alc_ins.*` entry points.
- Update all test suites, fixtures, and factory calls across `tests/`.

## Capabilities

### New Capabilities

*(None)*

### Modified Capabilities

- `plugin-packaging`: Update requirements and scenarios for entry point discovery (`alc_ins.*` prefix), distribution import package (`aiida_alc_ins`), and the module location of the exposed `__version__` attribute (`aiida_alc_ins.__version__` instead of `aiida_pythonjob_ins.__version__`). The version string itself is not modified.

## Non-goals

- **Bumping the package version**: The package version remains `0.2.0.dev0`; promoting to `0.2.0` is a separate release step following the documented release workflow.
- **Backward compatibility shims / alias redirects**: As agreed during release planning, this is a clean-break migration for 0.2.0. No legacy redirect aliases or deprecation shims for `aiida_pythonjob_ins` or `pythonjob_ins.*` will be retained.
- **Renaming the PyPI distribution**: The PyPI distribution is already `aiida-alc-ins` and remains unchanged.
- **Functional or scientific workflow changes**: No calculation logic, workflow logic, or data structures are changed.

## Impact

- **Public API**: Breaking change for any downstream users/callers of 0.1.0 importing `aiida_pythonjob_ins` or loading `WorkflowFactory("pythonjob_ins.*")` / `DataFactory("pythonjob_ins.*")`.
- **Source tree**: `src/aiida_pythonjob_ins/` moves to `src/aiida_alc_ins/`.
- **Configuration**: `pyproject.toml` entry points and `docs/source/conf.py` autoapi paths updated.
