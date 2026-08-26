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
environment, and have the child report what it observed on stdout.

- **Rationale**: This is the only way to observe what importing the operations
  actually causes, given the session-level configuration described in Context.
  It also satisfies the second existing scenario in `phonon-operations`
  ("Operations run with no AiiDA profile loaded") for free, since a child with
  no `AIIDA_PATH` and no imported AiiDA genuinely has no profile. AiiDA reads
  `AIIDA_PATH` to locate its configuration directory, so removing it is what
  makes the child's environment a faithful stand-in for a remote worker.
- **Alternatives considered**:
  - *Assert on `sys.modules` in-process*: vacuous, per Context. Measured: 171
    `aiida.*` modules are already loaded before the operations import.
  - *`importlib` in a fresh namespace within the same process*: `sys.modules`
    is process-global, so a module imported by any other test module would
    still be visible.
  - *Block the import in-process with `monkeypatch`* --- either
    `monkeypatch.setitem(sys.modules, "aiida", None)` or a `sys.meta_path`
    finder that raises --- then re-import the operations and expect
    `ImportError`. This is the in-process approach a reviewer is most likely to
    propose, and it produces a false pass on the most likely regression.
    `sys.modules` is consulted *before* both the sentinel on the parent package
    and any `meta_path` finder, so once the session has imported `aiida.orm`
    (which `conftest.py` guarantees), a later `from aiida.orm import Dict` is
    served from cache: the sentinel never sees it and the finder is never
    called. Measured: `import aiida`, `from aiida import orm` and
    `import aiida.orm` are all blocked, while `from aiida.orm import Dict`
    succeeds --- and `from aiida.<sub> import X` is the dominant import form in
    this codebase. The variant that removes AiiDA from `sys.modules` first is
    not available either: AiiDA is not reload-safe (memoized configuration,
    entry-point and ORM class caches) and modules holding references would keep
    the old objects, leaving two live copies of the package. `monkeypatch`
    reverses bindings; it cannot un-execute an import.
  - *Fork-based isolation (`pytest-forked` and similar)*: a forked child
    inherits the parent's `sys.modules`, so it starts with AiiDA already
    imported. Only a fresh interpreter (spawn/exec) observes the property under
    test.
  - *Static analysis of the import graph*: would catch direct imports but not
    transitive ones through a third-party package, which is the more likely
    regression. Verified with `import-linter`'s `forbidden` contract and
    `include_external_packages = True`: it correctly breaks on a direct
    `from aiida.orm import Dict` in the source module, but reports the contract
    KEPT when the same import is reached through an external package, because
    grimp records external packages as leaf nodes rather than traversing them.
    It would also add a dev dependency for a partial check.

### Decision 2: Observe with a recording `meta_path` finder, and report the import chain

The child's first action, before importing anything of its own, is to insert a
finder at the head of `sys.meta_path` whose `find_spec` records AiiDA module
names and returns `None`. Returning `None` means "I cannot handle this; carry
on" (https://docs.python.org/3/reference/import.html#the-meta-path), so the
finder observes without blocking. On the first AiiDA name it also captures
`traceback.extract_stack()`, and the child reports that stack as the blame
chain.

- **Rationale**: A check that reports only a verdict --- "AiiDA was loaded" ---
  leaves the reader to rediscover which of the transitive dependencies did it,
  and that is the objection usually raised against putting the check in a
  subprocess. It is avoidable: the child controls its own first line, so it can
  return evidence rather than a verdict. Measured against a synthetic violation
  three modules deep, the recorded chain names the file, line and source text of
  every hop from the operations module to the `from aiida.orm import ...` that
  caused it. No in-process technique can produce this, because in-process the
  import has already happened; and a subprocess that merely asserts cannot
  either. The traceability argument therefore favours this approach rather than
  counting against it.
- **Consequences**: record the *first* hit only and drop frames whose filename
  lies inside AiiDA itself. Measured: recording every hit yields several hundred
  entries, almost all of them AiiDA importing its own submodules, which buries
  the one frame that identifies the culprit.
- **Alternatives considered**:
  - *Report `sorted(m for m in sys.modules if ...)` and nothing else*: the
    original plan. Cheaper, but names only the symptom.
  - *`sys.addaudithook` on the `import` event*: also observes without blocking,
    but audit hooks cannot be removed once installed and the event fires after
    the import machinery has begun, so the stack is less direct. The finder is
    the narrower tool.
  - *Parse `python -X importtime` output*: the nesting does reveal chains, but
    it is a human diagnostic aid, not a stable machine-readable contract. Worth
    reaching for when investigating a failure; not worth asserting on.

### Decision 3: Hand back structured evidence over stdout, not a re-raised exception

The child exits zero and prints JSON; the parent decides pass or fail and
renders the message. On a non-zero exit the parent fails and includes the
child's stderr verbatim.

- **Rationale**: The child's job is to observe, not to judge, so what crosses
  the process boundary is data. Both failure modes stay legible: a contract
  violation produces the blame chain from Decision 2, and an unexpected crash
  produces the child's own traceback, unedited, inside the pytest failure.
- **Alternatives considered**:
  - *`ProcessPoolExecutor` with the `spawn` start method*: the child runs an
    ordinary function and exceptions return pickled with the remote traceback
    attached, which is the more idiomatic way to get a good failure message out
    of another process. Rejected because the advantage applies to exceptions,
    and here the interesting result is evidence rather than an exception; it
    also constrains the child (the target must be importable by name in a fresh
    interpreter, since `spawn` re-imports its module) and inherits `os.environ`,
    so `AIIDA_PATH` must be cleared in an `initializer` instead of simply being
    absent from the child's environment. Reconsider if the child ever needs to
    return rich Python objects.
  - *Fork-based isolation (`pytest-forked` and similar)*: a forked child
    inherits the parent's `sys.modules`, so it starts with AiiDA already
    imported. Only a fresh interpreter observes the property under test.

### Decision 4: Match AiiDA modules exactly, not by prefix

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

### Decision 5: Assert purity after execution as well as after import

In the same child, import the operations, check, call one operation, and check
again.

- **Rationale**: A lazy import inside a function body would pass an
  import-time-only check and still break a remote job. Re-checking after a call
  costs one extra assertion in a subprocess that has already paid the cost of
  importing the scientific stack.
- **Alternatives considered**: *Two separate subprocesses* — clearer separation,
  but doubles the dominant cost (importing Euphonic and NumPy) for no additional
  coverage.

### Decision 6: Assert absence of AiiDA only, not a permitted-import whitelist

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
