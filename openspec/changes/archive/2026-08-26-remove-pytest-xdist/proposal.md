# Remove the inert pytest-xdist dependency

## Why

`pytest-xdist` is declared in the `dev` dependency group but never enabled:
there is no `-n`, `--dist` or `numprocesses` setting in `pyproject.toml`, the
CI workflows or the docs. It is installed on every `uv sync` and does nothing.

Enabling it instead is not a micro-change. The suite has session-scoped fixtures
— the ephemeral AiiDA configuration directory, the AiiDA profile, and the
integration-test container — and under `xdist` each worker is a separate
process, so each would build its own. For the container that means one container
per worker, which is both slow and pointless. `pytest-xdist` documents a
`FileLock` pattern for exactly this case, but adopting it means adding fixture
machinery to integration tests that are about to be replaced.

Removing it now is free: a contributor who wants parallelism can run
`uv run --with pytest-xdist pytest -n auto` without the project declaring
anything. It also takes the parallel-execution question off the critical path of
the container rework, which no longer has to decide how to serialise jobs
against a scheduler-less computer.

## What Changes

- Remove `pytest-xdist>=3` from the `dev` dependency group in `pyproject.toml`.
- Record the ad-hoc invocation in the contributor-facing documentation, so the
  capability is discoverable without being declared.

## Capabilities

### New Capabilities

*(None)*

### Modified Capabilities

*(None. No requirement in `testing-and-ci` mentions parallel execution, and none
should: whether the suite runs on one process or many is a developer
convenience, not observable behaviour. `skip_specs: true` is set in
`.openspec.yaml`.)*

## Non-goals

- **Deciding against parallel testing.** This removes an unused declaration, not
  the option. Re-adoption is deferred to the investigation of a queueing
  scheduler for the integration tests, where the session-scoped-container
  problem must be solved anyway and where the speedup can be measured rather
  than assumed. `pytest-xdist` documents the `FileLock` approach for
  session-scoped fixtures that must execute only once:
  <https://pytest-xdist.readthedocs.io/en/stable/how-to.html#making-session-scoped-fixtures-execute-only-once>
- **Changing how any test is written, marked or collected.**
- **Changing CI.**

## Impact

- `pyproject.toml`: one line removed from `[dependency-groups].dev`.
- Contributor documentation: one line added.
- `uv.lock`: regenerated.

No source module, test, fixture, marker or workflow changes. The suite runs
exactly as it does today, because it already runs serially.
