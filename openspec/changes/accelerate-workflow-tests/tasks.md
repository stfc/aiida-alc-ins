# Tasks

## 1. Test Suite Concurrency Configuration

- [x] 1.1 Configure default test concurrency via `addopts = ["-n", "auto"]` in `pyproject.toml` under `[tool.pytest.ini_options]` and verify test suites (both non-containerized unit tests and containerized integration tests) execute cleanly with worker processes.

## 2. Consolidate Redundant TOSCA Tests

- [x] 2.1 Fold grouping line count assertions (`len(node1.outputs.spectrum.get_y()) == 3` and `len(results2["spectrum"].get_y()) == 2`) into `test_tosca_from_modes_regrouping_reuses_the_cached_intensities` in `tests/test_workflows.py`.
- [x] 2.2 Remove duplicate uncached test `test_tosca_from_modes_grouping_changes_line_count` from `tests/test_workflows.py`.

## 3. Shorten Multi-Step Exit-Code Tests

- [x] 3.1 Refactor `test_tosca_from_force_constants_failure_is_distinguishable` in `tests/test_workflows.py` to supply a prepared `ForceConstantsData` node created from `quartz_castep_bin`, skipping the preliminary CASTEP read step while verifying exit code `ERROR_SPECTRUM_WORKCHAIN_FAILED`.

## 4. Quality & Benchmark Verification

- [x] 4.1 Run `uv run ruff check` and `uv run ruff format --check` across `tests/` to verify lint and formatting compliance.
- [x] 4.2 Benchmark `tests/test_workflows.py` and verify reduced test suite execution walltime.

## 5. Documentation Updates

- [x] 5.1 Update testing instructions in `README.md` to reflect default parallel execution via `pytest-xdist` and document `-n 0` for sequential debugging.
- [x] 5.2 Update `docs/source/design_notes.rst` to reflect default `pytest-xdist` concurrency, file-locked container fixtures, and sequential execution with `-n 0`. Verify Sphinx documentation builds cleanly via `uv run --group doc make -C docs html`.
