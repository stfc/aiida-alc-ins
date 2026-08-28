## Why

`abinslib` version 0.2.0 has been released on PyPI, decoupling the atomic cross-section weighting step from intensity calculations into an explicit `apply_weights` function. In `abinslib` 0.1, intensity functions (`calculate_almost_isotropic_incoherent_spectra` and `mantid_like_combination_spectra`) returned pre-weighted spectra in barns. In `abinslib` 0.2.0, these functions return raw, unweighted spectra that callers must explicitly weight.

This change updates `aiida-pythonjob-ins` on the `main` branch to use `abinslib~=0.2.0` from PyPI, integrates `apply_weights` into `calculate_tosca_spectrum`, and keeps `main` cleanly focused on standard Python `>= 3.11`.

## What Changes

- **Dependency updates**: Update `pyproject.toml` on `main` to depend on `abinslib~=0.2.0` directly from PyPI and maintain `requires-python = ">=3.11"`.
- **Explicit Cross-Section Weighting**: In `aiida_pythonjob_ins.operations.calculate_tosca_spectrum`, call `apply_weights(raw_bank, key="scattering_cross_section")` on the raw `(fundamentals + combinations)` collection prior to `.group_by("atom_index", "quantum_order")`, restoring physical intensity units (`barn * cm` / `barn / cm^-1`).
- **Equivalence Tests**: Update `tests/test_operations.py::test_calculate_tosca_spectrum_matches_direct_abinslib_call` to include the `apply_weights` step in the direct reference calculation.
- **Documentation & Notes**: Update comments in `operations.py`, design notes, and docs tutorials to reference `abinslib 0.2.0`.

## Capabilities

### New Capabilities

*(None)*

### Modified Capabilities

- `tosca-spectra`: Updates the TOSCA intensity calculation to explicitly apply neutron scattering cross sections to unweighted raw spectra before grouping, ensuring physical intensity units.
- `plugin-packaging`: Updates dependency declarations to pin `abinslib~=0.2.0` and maintain standard `requires-python = ">=3.11"` packaging.

## Non-goals

- **Python 3.10 workarounds on `main`**: `main` remains clean with standard Python `>= 3.11` dependencies from PyPI. No version-conditional git repository sources (such as `@py310-0.2`) or backport shims will be added to `main`.
- **User-configurable weighting schemas in WorkChains**: Exposing customizable weighting options (e.g., incoherent-only vs total cross-section) in `ToscaFromModesWorkChain` is deferred to future workchain feature additions.

## Follow-ups

- **Rebase `py310` branch**: Following the merge of this change on `main`, rebase/recreate the `py310` branch of `aiida_pythonjob_ins` targeting `abinslib @ git+https://github.com/ISISNeutronMuon/abINS_lib@py310-0.2` and `resins @ git+https://github.com/pace-neutrons/resins@py310` for Python 3.10 runtime support.

## Impact

- **Affected Code**: `src/aiida_pythonjob_ins/operations.py`, `src/aiida_pythonjob_ins/conversions.py`, `tests/test_operations.py`, `pyproject.toml`, `docs/source/tutorials/`.
- **Dependencies**: `abinslib` bumped from `0.1.*` to `~=0.2.0`.
