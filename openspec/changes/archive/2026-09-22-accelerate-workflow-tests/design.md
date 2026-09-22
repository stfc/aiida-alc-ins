# Design: Accelerate workflow tests and scale test science problems

## Context

In `tests/test_workflows.py`, 13 tests take over 70s locally and ~120s on a 2-vCPU CI runner. The slowest tests are multi-step TOSCA, dispersion, and DOS workflows.

```
10.24s call  tests/test_workflows.py::test_tosca_from_force_constants_workchain
 9.11s call  tests/test_workflows.py::test_tosca_from_force_constants_failure_is_distinguishable
 7.69s call  tests/test_workflows.py::test_tosca_from_force_constants_accepts_a_prepared_node
 7.53s call  tests/test_workflows.py::test_tosca_from_modes_grouping_changes_line_count
 6.56s call  tests/test_workflows.py::test_dispersion_workchain
 6.13s call  tests/test_workflows.py::test_dos_workchain
```

## Decisions

### Decision 1: Test Suite Runner & Engine Latency Verification
- Empirical profiling confirmed `Runner._poll_interval = 0.0` and `aiida_localhost` poll interval is 0s by default under the test profile.
- Test suite runtime is primarily bounded by sequential execution of 23 `PythonJob` CalcJobs (~2.5–2.8s base overhead each from subprocess creation, Python interpreter startup, scientific library imports, and SQLite state commits).

### Decision 2: Shortcutting Multi-Step Setup in Exit-Code Tests
- In `test_tosca_from_force_constants_failure_is_distinguishable`, pass a prepared `ForceConstantsData` node instantiated directly from `quartz_castep_bin` (`ForceConstants.from_castep()`, taking ~0.11s in-memory).
- This skips the preliminary CASTEP-reading `PythonJob` (~2.8s) while testing mode interpolation and the delegated `ToscaFromModesWorkChain` failure, preserving the exact exit code assertion (`ERROR_SPECTRUM_WORKCHAIN_FAILED`, 401).

### Decision 3: Consolidate Redundant TOSCA Grouping Tests
- `test_tosca_from_modes_grouping_changes_line_count` ran two full uncached workflows (grouped by `atom_symbol` and `quantum_order`) taking ~7.3s.
- `test_tosca_from_modes_regrouping_reuses_the_cached_intensities` already executes those exact two workflows under caching.
- Fold the line count assertions (`len(node1.outputs.spectrum.get_y()) == 3` and `2`) directly into the caching test and remove `test_tosca_from_modes_grouping_changes_line_count`, saving ~7.3s without loss of coverage.

### Decision 4: Preserve Realistic Science Meshes in Dispersion and TOSCA Tests
- Keep 1D band paths for dispersion intact (~100 points along high-symmetry lines; linear scaling completes in <0.05s).
- Keep the 8-point 3D grid (`q_spacing=1.0`) in TOSCA Fourier interpolation to maintain zone-boundary and multi-q-point coverage without measurable performance penalty.
- Keep `src/` interfaces untouched; defer exposing `adaptive_method` or new workchain inputs to a dedicated feature issue.
