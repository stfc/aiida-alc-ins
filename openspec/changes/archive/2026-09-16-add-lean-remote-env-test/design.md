## Context

See `proposal.md` for motivation. The design-relevant constraints are:

- The standard library's `venv` can only clone the interpreter that runs it. A
  child environment therefore always has the parent's Python version unless a
  separate tool supplies another one.
- The job script `aiida-pythonjob` generates for this package imports only
  `sys`, `json`, `traceback`, `cloudpickle` and `node_graph`. This was
  established by running a real job in an environment containing neither
  `aiida-core` nor `aiida-pythonjob` (recorded in `proposal.md`), and is what
  makes an AiiDA-free child environment viable at all.
- Job codes in the suite are built with `aiida_code_installed` from
  `aiida.tools.pytest_fixtures`, which takes `filepath_executable`. Pointing a
  code at another interpreter therefore needs no new machinery.
- On aarch64 Linux, Euphonic is installed from a vendored wheel found via
  `find-links` under `[tool.uv]` in `pyproject.toml`. Tools other than `uv` do
  not read that setting.
- The suite already has a precedent for expensive, environment-dependent tests:
  the `containerized` marker, paired with runtime detection that skips rather
  than fails when the prerequisite is absent.

## Goals / Non-Goals

**Goals:**

- Keep one dependency list. The child environment's contents must follow from
  `pyproject.toml`, with no second list to drift.
- Make the cost opt-out-able and paid once per session.
- Fail loudly when the contract breaks, and skip cleanly when the platform
  cannot host the check at all — never pass by accident.

**Non-Goals:**

- Cross-version testing of submitting side against remote side. That needs a
  tool that can provision an arbitrary interpreter, and belongs with a `tox`
  orchestration layer if it is wanted later.
- Minimising the child environment. Uninstalling AiiDA leaves its dependencies
  behind; the environment is AiiDA-free, not small.

## Decisions

### Decision 1: Build the child environment with the standard library and pip, not `uv`

Create the environment with `venv` (bootstrapping `pip` via `ensurepip`) and
drive installation with the child interpreter's own `pip`.

- **Rationale**: `uv` would save roughly thirteen seconds per session, and costs
  more than it saves here for three reasons. A `uv`-created environment contains
  no `pip` unless seeded, so the choice is per-environment rather than
  per-command: whichever tool creates it must perform every later step, and
  there is no mid-way fallback. Supporting both therefore means two paths that
  both need continuous-integration coverage to stop the unused one rotting,
  which is most of the cost of having them. More importantly, `uv` and `pip`
  resolve dependencies independently, and the contract under test is precisely
  *"do the declared dependencies suffice for the remote side"* — two resolvers
  give two answers to that question, so a pass under one would not license a
  claim about the other. Finally, `uv`'s decisive advantage, provisioning an
  arbitrary Python with `--python`, is unused under Decision 2.
- **Alternatives considered**:
  - *Use `uv` when it is on `PATH`, else `pip`*: fastest in this project's usual
    setup, but introduces the dual-resolver ambiguity above and a second code
    path whose failures appear only on the legs that exercise it.
  - *Use `uv` and skip where it is absent*: makes coverage depend on developer
    tooling, and would skip in exactly the minimal environments where a missing
    runtime dependency is most likely to be noticed.
  - *Revisit later*: recorded as a deferred optimisation, to be reconsidered
    with the `tox` layer, where arbitrary interpreter versions are the point.

### Decision 2: The child interpreter is the parent's version; each CI leg covers its own

No version is requested or downloaded. The environment mirrors whichever Python
runs the suite, so the existing matrix covers four versions without any new
axis.

- **Rationale**: This is what `venv` does natively, so it costs nothing to
  implement and nothing to configure. It also keeps this change independent of
  `scope-ci-container-testing`, which is separately deciding how container legs
  are allocated.
- **Alternatives considered**: *Deliberately mismatch submitting and remote
  versions.* A real and interesting failure mode, but provisioning a second
  version requires a tool this design has just rejected, and orchestrating the
  combinations belongs in `tox`.

### Decision 3: Use the `venv` API, and confine subprocess use to two calls

Subclass `venv.EnvBuilder` and perform provisioning from its `post_setup(context)`
hook, taking the child interpreter from `context.env_exe`. Installation and
removal run as two subprocess calls of the form
`[context.env_exe, "-m", "pip", ...]`.

- **Rationale**: Environment creation needs no subprocess at all through the
  builder API. Installation does, unavoidably, for two independent reasons:
  `pip` publishes no supported Python API and documents `pip._internal` as off
  limits, and even were there one, an in-process call would act on the *calling*
  interpreter — installing into a different environment inherently means
  executing that environment's interpreter. Two calls is therefore the floor,
  not a shortcut. `context.env_exe` also supplies an absolute, platform-correct
  interpreter path, so the `bin` versus `Scripts` difference is handled by the
  standard library rather than by path arithmetic here.
- **Alternatives considered**:
  - *Drive `pip` in-process via its internals*: unsupported, and targets the
    wrong interpreter regardless.
  - *Collapse the two calls into one `-c` invocation*: trades a process for
    program text inside a string literal, which is harder to read, lint and
    debug — the opposite of the intent.
  - *Assemble the interpreter path by hand from `env_dir`*: reintroduces the
    per-platform branch the builder already resolves.

### Decision 4: Install the built distribution, then uninstall AiiDA

Install the project non-editable from the working tree, then uninstall
`aiida-core` and `aiida-pythonjob`.

- **Rationale**: A non-editable install exercises the built distribution, so a
  module missing from the packaged project is caught; an editable install would
  import straight from the source tree and prove nothing about packaging, which
  is half the failure mode this change exists to catch. Uninstalling afterwards
  keeps `pyproject.toml` the single source of truth: a curated install list
  would be a second dependency list, and the first thing it would do is drift.
  Removing both distributions rather than `aiida-core` alone is safe because
  `cloudpickle` and `node_graph` are separate distributions and survive the
  uninstall, and it makes the environment unambiguous.
- **Alternatives considered**:
  - *Install a hand-curated set of packages*: about thirteen seconds faster per
    session, at the price of the second list. Rejected on the same grounds the
    proposal gives.
  - *Uninstall `aiida-core` only*: sufficient to make `import aiida` fail, but
    leaves `aiida_pythonjob` importable-in-principle and the environment harder
    to describe.

### Decision 5: Assert the absence, before running anything

The fixture confirms in the child interpreter that both `import aiida` and
`import aiida_pythonjob` fail, and errors if either succeeds.

- **Rationale**: Every other assertion in this change is only meaningful if the
  environment really lacks AiiDA. Without this check, an uninstall that silently
  did nothing would leave a test that passes for exactly the reason it was
  written to rule out — the failure mode of the status quo, reproduced inside
  its own fix.

### Decision 6: Gate the cost behind a `venv_code` marker that runs by default

Register `venv_code` in `pyproject.toml`. Tests carrying it run by default and
are deselected with `-m "not venv_code"`.

- **Rationale**: The name states what the test does — the code points into a
  virtual environment — rather than how slow it happens to be, so it stays
  accurate if the cost changes. Running by default matches the `containerized`
  precedent and keeps the guarantee real: a contract that nothing exercises
  unless asked is not being enforced. The escape hatch covers the case the
  proposal names, where a developer iterating on unrelated code does not want to
  pay for it.
- **Alternatives considered**: *Deselect by default via `addopts`, opt in
  explicitly.* Cheaper by default, but it would mean the packaging contract is
  unverified on an ordinary run, and a regression would surface only in CI.

### Decision 7: One session-scoped environment, rebuilt each session

Build under `tmp_path_factory`, once per session, discarded at the end.

- **Rationale**: Simple and always correct. A cache keyed on the project's
  dependency declarations would remove the per-session cost, but a stale cache
  produces a *false pass* on precisely the contract under test, so it needs an
  invalidation rule that is right the first time.
- **Alternatives considered**: *Cache across runs.* Recorded as a deferred
  improvement, to be taken up once the fixture's shape has settled.

### Decision 8: Derive `find-links` from `pyproject.toml` rather than hard-coding it

Read `[tool.uv] find-links` with `tomllib` and pass it to the child install,
instead of writing `wheels` into the test code.

- **Rationale**: The aarch64 vendored-wheel workaround is temporary and will be
  deleted when a wheel reaches PyPI. Hard-coding the path here would create a
  second site to remember; reading the value means deleting the `[tool.uv]`
  block automatically stops the child install passing it. The workaround stays
  single-source and removes itself.
- **Alternatives considered**:
  - *Hard-code `wheels` with a cross-referencing comment*: relies on a future
    reader following the comment.
  - *Skip the check on aarch64*: silently drops coverage on a platform the
    project explicitly supports.

### Decision 9: Skip when the platform cannot host the environment

Where `ensurepip` is unavailable — some distribution-packaged interpreters omit
it — skip with a clear message rather than failing.

- **Rationale**: Mirrors the container-engine detection already in the suite,
  and matches the spec's own scenario. The alternative punishes environments
  that cannot host the check for reasons unrelated to the code under test.

### Decision 10: Parametrise an existing job test, and add one dedicated precondition test

Parametrise the fixture that supplies a job code so an existing job test runs
against both interpreters, and add a small test asserting the child environment
lacks AiiDA.

- **Rationale**: Parametrisation gives the equivalence scenario for free: the
  same assertions run against both interpreters, so there is no second copy of
  the expected results to maintain, and any divergence between the two
  environments shows up as a plain test failure. The dedicated test exists
  because Decision 5's precondition deserves to be named in the report rather
  than buried in fixture setup.

## Risks / Trade-offs

- **[Risk] The uninstall removes something the remote genuinely needs.**
  `cloudpickle` and `node_graph` are separate distributions and should survive,
  but this is reasoning about a packaging graph, not a measurement.
  → *Mitigation*: verify at implementation; the job itself is the check, and it
  fails loudly with `ModuleNotFoundError` naming the missing module if the
  reasoning is wrong.

- **[Risk] `pip` bootstrapped by `ensurepip` may be substantially older than the
  `pip`/`uv` used in development**, and may resolve or build differently.
  → *Mitigation*: accepted for now; upgrading it costs time on every session and
  would make the child less representative of a plainly provisioned machine, not
  more. Recorded as an open question.

- **[Trade-off] The resolver under test is `pip`'s, while development uses
  `uv`'s.** A dependency declaration that satisfies one could in principle fail
  the other. This is a narrower guarantee than it may appear, and is stated here
  so it is not later mistaken for full coverage.

- **[Trade-off] Roughly twenty-six seconds are added to a default session**,
  once, plus about five per job exercised.
  → *Mitigation*: session scope, a single environment, and the `venv_code`
  marker for opting out.

- **[Risk] Orphaned AiiDA dependencies remain installed**, so the environment
  resembles a compute node less closely than "AiiDA-free" might suggest.
  → *Mitigation*: none needed for the contract under test, but the environment
  should not be described as lean anywhere in code or documentation.

## Migration Plan

Not applicable. The change is confined to the test suite: there is nothing to
deploy, and reverting is deleting the fixture, the marker registration and the
parametrisation.

## Open Questions

- Whether to upgrade `pip` inside the child environment after bootstrapping,
  trading a few seconds for a more current resolver.
- Whether the cached-environment variant of Decision 7 is worth its invalidation
  rule, and what that rule keys on.
