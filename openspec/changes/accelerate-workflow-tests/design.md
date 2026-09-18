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

### Decision 1: Aggressive transport and computer polling in test fixtures
- In `conftest.py`, ensure test computers (`aiida_localhost`, `remote_computer`) configure `set_minimum_job_poll_interval(0.1)` and `safe_interval = 0.0`.
- Verify runner polling frequency is tuned for test execution rather than production cluster conservativeness.

### Decision 2: Minimal science workloads for structural and exit-code tests
- `test_tosca_from_force_constants_failure_is_distinguishable`: Currently runs a full CASTEP read and mode interpolation before failing in the delegated spectrum workchain. Providing a pre-computed or minimal mock/small `modes` input, or bypassing the heavy force constants read step, saves ~7–8s in this test alone.
- Use coarser q-spacing (e.g. `q_spacing=Float(1.5)` or `Float(2.0)`) and energy bin widths in tests whose assertions verify node types, output counts, or exit statuses rather than numeric integration convergence.

### Decision 3: Expose configurable parameters where needed
- If any internal workflow step hardcodes sampling densities or bounds that prevent callers from scaling down problem sizes, expose them as optional inputs with sensible defaults matching existing behavior.
