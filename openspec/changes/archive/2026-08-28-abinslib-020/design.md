## Context

`abinslib` version 0.2.0 has been released on PyPI, decoupling cross-section weighting from intensity calculations. Intensity routines (`calculate_almost_isotropic_incoherent_spectra` and `mantid_like_combination_spectra`) now return unweighted spectra (`1 / energy`), and `abinslib.util.apply_weights` must be invoked to apply elemental/isotopic neutron scattering cross sections.

See `proposal.md` for background and motivation.

## Goals / Non-Goals

**Goals:**
- Update `aiida_pythonjob_ins` on `main` to use `abinslib~=0.2.0` from PyPI.
- Ensure `calculate_tosca_spectrum` produces fully weighted physical spectra with units `barn * cm` (or `barn / cm^-1`).
- Maintain clean plot legend labels by filtering non-distinguishing atom metadata.
- Keep `main` clean and standard with `requires-python = ">=3.11"` and standard PyPI dependencies.

**Non-Goals:**
- Introducing Python 3.10 conditional git sources or backport shims on `main` (deferred to a follow-up rebase of the `py310` branch).
- Exposing user-configurable weighting schemes (e.g. unweighted or incoherent-only) in `ToscaFromModesWorkChain`.

## Decisions

### Decision 1: Apply `apply_weights` before `group_by` in `calculate_tosca_spectrum`
- **Choice**: Call `apply_weights(raw_bank, key="scattering_cross_section")` on the un-grouped `(fundamentals + combinations)` collection prior to `.group_by("atom_index", "quantum_order")`.
- **Rationale**: The raw collection is guaranteed to contain intact `atom_symbol` and `mass` metadata on every line, generated directly from `iter_atom_info(modes.crystal)`. Applying weights before grouping avoids any dependency on `group_by` preserving specific metadata fields.
- **Alternatives Considered**: Applying `apply_weights` after grouping was considered; rejected because it is safer to bind weighting directly to the raw atomic line descriptions.

### Decision 2: Two-Phase Rollout Strategy for `abinslib 0.2` and Python 3.10
- **Choice**: Update `main` with standard `requires-python = ">=3.11"` and standard PyPI dependencies (`abinslib~=0.2.0`), deferring Python 3.10 compatibility to a follow-up `py310` branch.
- **Rationale**: Prevents polluting `main` with conditional git URLs or backport dependencies. Once `main` is validated and merged, the `py310` branch will be rebased and configured with `abinslib@py310-0.2` and `resins@py310`.

### Decision 3: Retain `'mass'` in legend label generation
- **Choice**: Keep `'mass'` in legend label generation rather than unconditionally excluding it in `_LABEL_EXCLUDED_KEYS`.
- **Rationale**: In systems with isotopic substitution, when lines are grouped by `(symbol, mass)` or when isotopic lines are distinguished, `'mass'` provides essential information to differentiate distinct isotopes (e.g. distinguishing `H` with mass 1.008 from deuterium with mass 2.014). Unconditionally excluding `'mass'` would cause legend label collisions for distinct isotopic lines. Context-dependent label filtering (e.g. omitting `'mass'` unless it was a grouping parameter) is deferred to future plotting enhancements.

### Decision 4: Encapsulate weighting inside `calculate_tosca_spectrum`
- **Choice**: Call `apply_weights` directly within `calculate_tosca_spectrum` so that the `components` `XyData` node committed to the AiiDA provenance graph always holds physical intensities in barns.
- **Rationale**: Keeps the PythonJob output physically meaningful and preserves downstream workchain operations (`group_spectra` and `broaden_spectra`) unchanged.

## Risks / Trade-offs

- **[Risk]** Unweighted intensities could silently pass through if `apply_weights` is omitted.
  - **Mitigation**: Unit tests and equivalence tests explicitly verify that `spectrum.y_data.units` has `barn` dimensions and compare against direct `abinslib` reference values.
- **[Risk]** `pyproject.toml` resolution differences between development environments.
  - **Mitigation**: Standard `abinslib~=0.2.0` on PyPI resolves cleanly on all supported platforms with no local wheel workarounds needed on x86_64.
