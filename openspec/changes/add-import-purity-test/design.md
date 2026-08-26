## Context

See `proposal.md` for motivation. Two facts about the existing suite shape the
approach and are easy to overlook:

- `tests/conftest.py` sets `AIIDA_PATH` and calls `get_config(create=True)` at
  module scope, before collection, because `aiida-pythonjob` reads AiiDA
  configuration at import time. Every test therefore runs in a process where
  AiiDA is both imported and configured.
- `tests/test_operations.py` imports `aiida.engine`, `aiida.orm` and
  `aiida_pythonjob` at module scope.

Any assertion made inside the test session about which modules are loaded is
therefore an assertion about the *session*, not about the operations.

## Goals / Non-Goals

**Goals:**

- Make a violation fail fast and name its cause, rather than surfacing later as
  a `ModuleNotFoundError` inside a job script on a compute node.
- Keep the check runnable everywhere the suite runs: no container engine, no
  network, no extra dependency, no marker.

**Non-Goals:**

- Detecting packaging or dependency-resolution problems in a remote
  environment. That is a different failure mode requiring a separate
  environment, and is being explored separately.

## Decisions

### Decision 1: Run the check in a subprocess with a cleaned environment

Launch `sys.executable` with `subprocess`, removing `AIIDA_PATH` from the child
environment, and have the child report the loaded AiiDA modules on stdout.

- **Rationale**: This is the only way to observe what importing the operations
  actually causes, given the session-level configuration described in Context.
  It also satisfies the second existing scenario in `phonon-operations`
  ("Operations run with no AiiDA profile loaded") for free, since a child with
  no `AIIDA_PATH` and no imported AiiDA genuinely has no profile. AiiDA reads
  `AIIDA_PATH` to locate its configuration directory, so removing it is what
  makes the child's environment a faithful stand-in for a remote worker.
- **Alternatives considered**:
  - *Assert on `sys.modules` in-process*: vacuous, per Context.
  - *`importlib` in a fresh namespace within the same process*: `sys.modules`
    is process-global, so a module imported by any other test module would
    still be visible.
  - *Static analysis of the import graph*: would catch direct imports but not
    transitive ones through a third-party package, which is the more likely
    regression.

### Decision 2: Match AiiDA modules exactly, not by prefix

Treat a module as AiiDA only when its name is `aiida` or begins with `aiida.`.

- **Rationale**: This package's own import name begins with the same letters, so
  a naive prefix match reports a false positive and the test fails
  unconditionally. Measured on the current tree: the exact match reports no
  AiiDA modules, while a prefix match reports this package's own module. The
  distinction is subtle enough that the spec states it as a scenario in its own
  right.
- **Alternatives considered**: *Exclude this package by name* — works, but
  couples the check to the current package name; matching the dotted namespace
  is the property that actually matters.

### Decision 3: Assert purity after execution as well as after import

In the same child, import the operations, check, call one operation, and check
again.

- **Rationale**: A lazy import inside a function body would pass an
  import-time-only check and still break a remote job. Re-checking after a call
  costs one extra assertion in a subprocess that has already paid the cost of
  importing the scientific stack.
- **Alternatives considered**: *Two separate subprocesses* — clearer separation,
  but doubles the dominant cost (importing Euphonic and NumPy) for no additional
  coverage.

### Decision 4: Assert absence of AiiDA only, not a permitted-import whitelist

- **Rationale**: The contract is about AiiDA. A whitelist would restate the
  dependency declaration in a second place and would fail whenever a transitive
  dependency changed its own imports, which is noise rather than signal.

## Risks / Trade-offs

- **[Risk] The check passes while remote execution is still broken**, because
  import purity says nothing about whether the distribution is complete or its
  dependencies resolve in a foreign environment.
  → *Mitigation*: state the boundary in the proposal's non-goals, and leave
  those failure modes to the environment-based coverage being explored
  separately. This check is deliberately the cheapest layer, not the only one.

- **[Risk] Subprocess start-up plus importing the scientific stack makes the
  check noticeably slower than a unit test.**
  → *Mitigation*: one subprocess covers both scenarios; the cost is bounded by a
  single Euphonic import, which the suite already pays many times over.

- **[Trade-off] Using `sys.executable` means the check runs in the development
  environment, where the package and its dependencies are installed.** It
  therefore tests the import chain, not a lean environment. That is the intended
  division of labour, but it means a green result must not be read as evidence
  that a remote environment would work.
