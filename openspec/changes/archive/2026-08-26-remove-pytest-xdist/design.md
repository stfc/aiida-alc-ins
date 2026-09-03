## Context

See `proposal.md` for the motivation behind removing `pytest-xdist`.

The project manages developer dependencies through `pyproject.toml`'s `[dependency-groups].dev` and locks them with `uv.lock`. Tests currently execute serially across all environments (local development and CI workflows). Session-scoped fixtures (e.g., ephemeral AiiDA configuration and containerized test fixtures) assume a single-process execution model.

## Goals / Non-Goals

**Goals:**
- Eliminate the inert `pytest-xdist>=3` dependency from `[dependency-groups].dev`.
- Update `uv.lock` to reflect the trimmed dependency graph.
- Document the ad-hoc invocation (`uv run --with pytest-xdist pytest ...`) for contributors wanting local test parallelism.

**Non-Goals:**
- Implement worker synchronization or `FileLock` mechanisms for session-scoped fixtures.
- Modify CI test execution commands or pytest default flags.
- Alter any test logic, fixtures, or markers.

## Decisions

### Decision: Remove `pytest-xdist` from `dev` dependencies rather than configuring `-n auto`

- **Rationale**: `pytest-xdist` is currently declared but unused. Configuring `-n auto` across the whole suite introduces worker-isolation issues for session-scoped fixtures (such as containerized integration tests) without inter-process locking. Removing the unconfigured dependency keeps the dev environment lean while `uv`'s `--with` flag makes ad-hoc parallel runs trivial on demand.
- **Alternatives considered**:
  - *Keep `pytest-xdist` installed and unconfigured*: Carries dead dependency weight in `uv.lock` and creates a false expectation that tests are fully xdist-ready.
  - *Configure `pytest-xdist` with `FileLock` synchronization*: Requires fixture refactoring (per the [pytest-xdist session-scoped fixture recipe](https://pytest-xdist.readthedocs.io/en/stable/how-to.html#making-session-scoped-fixtures-execute-only-once)) ahead of planned container test rework.

### Decision: Document ad-hoc execution via `uv run --with pytest-xdist`

- **Rationale**: `uv` natively supports ephemeral dependencies via `uv run --with <pkg>`. Contributors running non-containerized unit test slices can execute `uv run --with pytest-xdist pytest -n auto -m "not containerized"` without requiring `pytest-xdist` in the main workspace dependency tree.
- **Alternatives considered**:
  - *Add a separate optional dependency group (e.g. `[dependency-groups].parallel`)*: Adds dependency-group maintenance overhead for a simple ad-hoc CLI capability.

## Risks / Trade-offs

- [Contributor expects parallel test execution by default] → Document the ad-hoc command (`uv run --with pytest-xdist pytest -n auto -m "not containerized"`) in contributor documentation.
- [Ad-hoc xdist run executes containerized tests and encounters race conditions] → Explicitly note in documentation that containerized tests (`-m "not containerized"`) must be excluded under ad-hoc xdist execution until container fixtures are made process-safe.
