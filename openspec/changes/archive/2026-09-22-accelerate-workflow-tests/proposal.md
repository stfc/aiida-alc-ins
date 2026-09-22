# Accelerate workflow tests and scale test science problems

## Why

The workflow test suite (`tests/test_workflows.py`) accounts for the single largest runtime component of the test suite, taking ~70 seconds locally and over 2 minutes in CI across 13 test cases.

This execution time stems from two primary factors:
1. **Engine Polling Overhead**: Every `PythonJob` CalcJob launched under an AiiDA WorkChain transitions through process states (`WAITING` -> `SUBMITTING` -> `RUNNING` -> `MONITORING` -> `PARSING`) with default sleep intervals. For multi-step workchains, the process engine spends seconds in sleep loops regardless of computation time.
2. **Heavy Science Workloads for Structural Checks**: Several tests that only verify wiring, input validation, or failure exit codes (such as `test_tosca_from_force_constants_failure_is_distinguishable`) execute heavy multi-step phonon interpolations across Quartz (9 atoms, 27 branches) before triggering the condition under test.

Accelerating polling intervals on the test computer, scaling down test science problems to minimal representative grids, and exposing configurable parameters where workflows currently lack them will drastically reduce test suite duration without compromising verification rigor.

## What Changes

- Optimize AiiDA process runner and computer polling intervals in test fixtures (e.g. `set_minimum_job_poll_interval`).
- Scale down science problem sizes across workflow tests using coarse q-spacing and energy grids where physical accuracy is not the assertion target.
- For exit-code and error-handling tests, avoid full pre-computation pipelines by supplying prepared intermediate nodes or minimal test structures.
- Expose any missing workflow parameters needed by callers and test suites to tune problem dimensions cleanly.

## Capabilities

### New Capabilities

*(None)*

### Modified Capabilities

*(None - behavioral requirements in `phonon-workflows` and `testing-and-ci` are unchanged; `skip_specs: true` is set)*

## Non-goals

- Relaxing scientific assertions or tolerances in existing tests.
- Mocking out the AiiDA engine or replacing real `PythonJob` executions with dummy stubs in end-to-end integration tests.

## Impact

- `tests/test_workflows.py`: Coarser sampling parameters and streamlined test structures.
- `tests/conftest.py`: Fast polling configuration for test computers and runners.
- Significantly cuts CI and local test execution times.
