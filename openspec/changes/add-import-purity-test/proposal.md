# Verify that the operations import chain stays free of AiiDA

## Why

`phonon-operations` already requires that nothing in the operations import chain
imports AiiDA, and states two scenarios that read exactly like tests. Neither is
implemented. The behaviour itself is correct today — a `PythonJob` was confirmed
to run in a virtual environment containing neither `aiida-core` nor
`aiida-pythonjob` — so this change adds the missing verification of an existing,
already-satisfied requirement rather than proposing new behaviour.

The gap matters because the claim is load-bearing and silently breakable. Any
convenience import added to `operations.py`, or to anything it imports, would
make every remote job fail with a `ModuleNotFoundError` raised inside a job
script on a compute node — an expensive place to discover it. A regression is
also invisible to the existing suite: `tests/test_operations.py` imports
`aiida.engine`, `aiida.orm` and `aiida_pythonjob` at module scope, and
`tests/conftest.py` configures AiiDA before collection, so by the time any
current test runs, AiiDA is loaded regardless of what `operations.py` does.

## What Changes

- Add a test module that verifies the requirement in a **subprocess** started
  with a clean environment, covering both existing scenarios:
  - importing the operations module loads no AiiDA module;
  - an operation called directly returns its Euphonic result with no AiiDA
    profile present.
- Add a requirement to `testing-and-ci` recording that this contract must be
  verified out-of-process. Without that constraint, a later simplification to an
  in-process assertion would leave a test that passes unconditionally.

## Capabilities

### New Capabilities

*(None)*

### Modified Capabilities

- `testing-and-ci`: add a requirement that the AiiDA-independence contract is
  verified in a subprocess which has not itself imported or configured AiiDA, so
  the check cannot be satisfied vacuously by the test session's own state.

*(`phonon-operations` is deliberately unchanged: its requirement and both of its
scenarios already state the contract correctly. This change implements them.)*

## Non-goals

- **Changing `operations.py` or anything it imports.** The contract already
  holds; this change only guards it.
- **Verifying that the package is installable or resolvable in a foreign
  environment.** Import purity and remote installability are different failure
  modes; the latter needs a separate environment and is being explored
  separately.
- **Asserting anything about which third-party modules the operations load.**
  Only the absence of AiiDA is in scope; a whitelist of permitted imports would
  be brittle and would duplicate the dependency declaration.
- **Replacing any existing test.** `tests/test_operations.py` continues to cover
  scientific behaviour in-process.

## Impact

- `tests/`: one new test module. No fixture, marker, dependency or
  configuration change; it runs everywhere the suite already runs, needs no
  container engine and no network.
- `openspec/specs/testing-and-ci/spec.md`: one added requirement.
- No source module, dependency, entry point or public API is touched.
