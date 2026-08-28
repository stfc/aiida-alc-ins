## 1. Dependency Configuration

- [x] 1.1 Update `pyproject.toml` to declare `abinslib~=0.2.0` from PyPI, restore `requires-python = ">=3.11"`, and verify with `uv lock --upgrade-package abinslib`.

## 2. Core Implementation

- [x] 2.1 Update `src/aiida_pythonjob_ins/operations.py` to import `apply_weights` from `abinslib.util` and invoke `apply_weights(raw_bank, key="scattering_cross_section")` on `(fundamentals + combinations)` prior to `.group_by("atom_index", "quantum_order")` in `calculate_tosca_spectrum`.
- [x] 2.2 Refresh comments and docstrings in `src/aiida_pythonjob_ins/operations.py` to cite `abinslib 0.2` decoupled weighting.

## 3. Test Suite and Equivalence Verification

- [x] 3.1 Update `tests/test_operations.py::test_calculate_tosca_spectrum_matches_direct_abinslib_call` to include `apply_weights` in the direct reference calculation.
- [x] 3.2 Add test assertions verifying that `calculate_tosca_spectrum` outputs spectra with physical units containing `barn` dimensions and that multi-atom / isotopic collections generate valid labels.
- [x] 3.3 Run `uv run pytest` across the test suite and verify all tests pass with 0 failures.

## 4. Documentation and Linting

- [x] 4.1 Refresh tutorial notes in `docs/source/tutorials/plot_tosca_from_force_constants.py` and `plot_tosca_from_modes.py` to reflect `abinslib 0.2`.
- [x] 4.2 Run `uv run ruff check` and `uv run ruff format --check` and verify all style and import checks pass.
- [x] 4.3 Run `uv run --group doc make -C docs html` and verify documentation builds without warnings.
