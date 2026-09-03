# Run container tests on one CI leg, with a selectable remote Python

> **Status: proposal only.** Recorded so the investigation behind it is not
> lost. `specs/`, `design.md` and `tasks.md` are not yet written, so this change
> does not validate. Depends on `replace-slurm-container-with-ssh`, whose fixture
> determines what CI must invoke.

## Why

Continuous integration runs the suite across Python 3.11, 3.12, 3.13 and 3.14,
and the containerized tests run on all four. The image bakes a single Python
version regardless, so three of those four legs build an image and start a
container to test nothing that the fourth does not already cover. The cost is
paid on every pull request.

Meanwhile the thing that *would* be worth varying is not varied at all: the
version of Python in the remote environment, relative to the submitting side.
A mismatch between the two is an ordinary situation on real clusters, and it is
exactly the kind of difference that a by-reference execution model can be
sensitive to. Making it a parameter turns a wasted axis into a useful one.

## What Changes

- Run containerized tests on a single matrix leg; deselect them elsewhere with
  the existing marker.
- Introduce a build argument controlling the remote environment's Python
  version, with a workflow input so it can be varied deliberately without
  expanding the matrix.
- Decide and record whether the container leg deliberately runs a *different*
  submitting-side Python from the remote one, so that mismatch is exercised by
  default rather than only on request.

## Capabilities

### Modified Capabilities

- `testing-and-ci`: the continuous-integration requirement currently states that
  the suite runs across the full Python matrix. It needs to distinguish the
  matrix that applies to the whole suite from the single leg on which
  container-backed tests run, and to record that the remote interpreter version
  is a parameter.

## Non-goals

- **Changing the Python version matrix for the suite as a whole.**
- **Adding caching of container images or Python environments.** Worth
  considering separately; measurements first — a cold dependency install into a
  fresh environment was around thirteen seconds, so caching may not be where the
  time goes.
- **Introducing scheduled or release-gated workflows.** The Slurm walkthrough is
  documentation, not CI.

## Impact

- `.github/workflows/ci.yml`, the container build definition, and the fixture
  that reads the remote Python version.
- `openspec/specs/testing-and-ci/spec.md`.
- Reduces per-pull-request CI work by roughly three container builds and runs.

## Open questions

- Which leg carries the container tests, and whether it is chosen to create a
  submitting/remote version mismatch.
- Whether the remote Python version should default to the lowest supported
  version rather than the newest, on the grounds that clusters lag.
