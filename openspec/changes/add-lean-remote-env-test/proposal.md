# Run a PythonJob in an environment that has no AiiDA

## Why

`pythonjob-execution` requires that job functions are shipped by module
reference, and states that the execution environment "must therefore have this
package importable, alongside the scientific dependencies the function uses".
Nothing verifies that. Every job test today points its `InstalledCode` at
`sys.executable`, so the "remote" interpreter is the same virtual environment as
the test session: the import always resolves, and it resolves for reasons that
would not hold anywhere else.

This is a different failure mode from the import-purity check added in
`add-import-purity-test`. That check runs in the development environment and
proves the import chain touches no AiiDA. It cannot detect a distribution that
omits a module, a runtime dependency declared only as a development dependency,
or a by-reference payload that fails to unpickle where the submitting side's
packages are absent. Those surface as a `ModuleNotFoundError` raised inside a job
script on a compute node.

A containerized integration test would also cover this, but only in continuous
integration and only where a container engine is available — which excludes
sandboxed development environments, where a nested rootless engine cannot accept
SSH logins at all. A second virtual environment on the same machine covers the
same contract in seconds, everywhere, with no engine and no network.

The mechanism was verified before proposing it: a `PythonJob` reading force
constants ran to completion in a virtual environment containing neither
`aiida-core` nor `aiida-pythonjob`, confirming that the remote side needs only
`cloudpickle`, `node_graph`, this package and its scientific dependencies.

## What Changes

- Add a session-scoped fixture that builds a second virtual environment using
  the standard library's `venv` module and the `pip` it bootstraps, so no
  additional tool is required. Where `ensurepip` is unavailable the fixture
  skips cleanly, in the same manner as the existing container-engine detection.
- Populate that environment by installing the project normally and then
  removing AiiDA from it, rather than from a hand-maintained list of packages.
  This keeps `pyproject.toml` the single source of truth for what the remote
  needs, and avoids a second dependency list that can drift.
- Add a code fixture whose executable is that environment's interpreter, and
  exercise at least one existing `PythonJob` against it, so the by-reference
  payload must resolve in an interpreter that shares nothing with the test
  session.
- Record in `testing-and-ci` that remote execution is verified against an
  interpreter other than the one running the tests.

## Capabilities

### New Capabilities

*(None)*

### Modified Capabilities

- `testing-and-ci`: add a requirement that by-reference job execution is
  verified against a separate interpreter which does not have AiiDA available,
  so that the resolution of the function reference is genuinely exercised rather
  than satisfied by the test session's own environment.

## Non-goals

- **Replacing the containerized integration test.** This covers a foreign
  *interpreter*, not a foreign *machine*: no SSH transport, no file staging over
  a network, no scheduler. Those remain the container's job.
- **Producing a minimal environment.** Removing AiiDA leaves its dependencies
  behind as orphans. The environment is AiiDA-free, which is the contract under
  test; it is not lean, and should not be described as such.
- **Testing installation from a package index.** The environment is built from
  the working tree, so the code under test is the code in the branch.
- **Replacing the import-purity check**, which is far cheaper and names the
  cause of the most likely regression directly.

## Impact

- `tests/`: one new fixture module or conftest addition, plus parametrisation of
  at least one existing job test. No new project dependency: the standard
  library provides `venv`, and `pip` is bootstrapped into the child environment.
- `openspec/specs/testing-and-ci/spec.md`: one added requirement.
- No source module, dependency, entry point or public API is touched.

Measured during investigation, on x86-64 Linux with the project's own
interpreter, so the design need not re-derive them:

| Step | Time |
| --- | --- |
| Create the environment with the standard library `venv` module | ~2 s |
| Install the project into it, cold, with the package cache bypassed | ~26 s |
| Install a hand-curated equivalent set instead, cold | ~13 s |
| Remove AiiDA from the installed environment | <1 s |
| Run one `PythonJob` against it | ~5 s |

Installing the project and then removing AiiDA costs roughly thirteen seconds
more than curating a list by hand. That is the price of having one dependency
list rather than two, and it is paid once per session.
