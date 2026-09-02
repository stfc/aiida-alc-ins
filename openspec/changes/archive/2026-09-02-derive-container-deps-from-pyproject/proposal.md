## Why

The integration container's dependency list is hand-maintained in
`tests/container/Dockerfile`, duplicating the runtime dependencies already
declared in `pyproject.toml`. The two drifted: `pyproject.toml` moved to
`abinslib~=0.2.0` while the Dockerfile stayed on `abinslib==0.1.*`.

Because `aiida-pythonjob` ships job functions *by reference*, unpickling one on
the remote executes `operations.py`'s module-level imports, which now include
`from abinslib.util import apply_weights` — absent from abinslib 0.1. Every
remote job therefore failed with an `ImportError`, including jobs that never
touch the TOSCA code that motivated the bump.

**That breakage is already fixed.** Commit `a37f5e0` bumped the Dockerfile's pin
to `abinslib==0.2.*` and dropped `--no-deps` from the fixture's runtime install
so the container reconciles its own dependencies at start-up; `4dd6687` cleared
the unrelated `ruff format` failure that was gating the CI test job. This change
is therefore not about restoring a green suite — it is about the cause, which is
untouched.

The drift was structurally guaranteed rather than an oversight. The image is
built with `tests/container/` as its build context, so `pyproject.toml` is not
reachable from the Dockerfile even in principle, and no rebuild is triggered
when the declared dependencies change. The hand-written list is still there,
still a second statement of versions already declared elsewhere, and still free
to drift again at the next bump — the runtime reconciliation now masks the
symptom rather than removing the cause.

## What Changes

- Move the container build context from `tests/container/` to the project root,
  so the Dockerfile can read `pyproject.toml`.
- `COPY pyproject.toml` into the image and install the container's baked
  dependencies from it, deleting the hand-written package list. Container
  dependency provisioning gains a single source of truth, and editing
  `pyproject.toml` invalidates the cached image layer — which is the correct
  trigger, at release-or-dependency-change frequency.
- Add a `.containerignore` written as an *allowlist* — exclude everything, then
  re-include `pyproject.toml`, `wheels/` and `tests/container/`. The build needs
  32 KB; the unfiltered root is 526 MB, and a denylist of the obvious offenders
  still leaves 6.8 MB. An allowlist cannot rot as the tree grows.
- Shrink the built image by the two means available without changing what is
  tested: install with `uv pip install --no-cache`, and drop `sudo` (installed
  but never invoked) along with `python3-pip` / `python3-venv` (needed only to
  bootstrap uv, which can instead be copied from its published image).
- Update the `COPY` source paths for `id_rsa.pub`, `slurm.conf` and
  `entrypoint.sh`, which become `tests/container/`-relative under the new
  context.
- `COPY wheels/` alongside `pyproject.toml`: `[tool.uv] find-links = ["wheels"]`
  is unconditional, and uv aborts with `Failed to read --find-links directory`
  when the directory is absent.
The fixture's runtime install is left as `a37f5e0` set it, without `--no-deps`.
Restoring the flag once the baked layer derives from `pyproject.toml` would save
a redundant dependency resolution at every container start, but that saving has
not been measured and the reconciliation is currently the thing keeping the
container correct. Deferred deliberately rather than settled — see design.md
Decision 4.

## Non-goals

- **Adding any dependency check at container start.** Asserting that the
  container's environment satisfies the manifest — or matches the host's
  resolution — would turn a silent `ImportError` into a legible failure. While
  the fixture keeps re-resolving dependencies at start-up there is nothing for
  such a check to catch, so it is tied to the deferred `--no-deps` question
  rather than to this change (design.md Decision 4).
- **Reducing how often CI builds the image.** CI currently runs the
  containerized tests on all four Python legs. That is
  `scope-ci-container-testing`'s subject.
- **Removing the Slurm layer, or covering the lean-remote-environment
  contract.** `replace-slurm-container-with-ssh` and `add-lean-remote-env-test`
  own those. Neither would have caught this drift: a child environment built
  from `pyproject.toml` gets abinslib 0.2 and passes.
- **Changing which project dependencies the container holds.** Installing from
  `pyproject.toml` reproduces the current set, `aiida-core` included. Whether
  the remote needs AiiDA at all is `replace-slurm-container-with-ssh`'s
  question — worth about 285 MB, measured and recorded in design.md so that
  change can be argued on evidence rather than reopened here.
- **Pinning the container to the host's lockfile.** See design.md; constraint
  parity is chosen deliberately over lockfile parity.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `testing-and-ci`: adds a requirement that the containerized test
  environment's dependencies derive from the project's declared dependencies,
  and that a change to those declarations is reflected in the environment
  rather than silently ignored.

## Impact

- `tests/container/Dockerfile` — build context, `COPY` paths, dependency
  install step, apt package list, uv acquisition.
- `tests/slurm_support.py` — `ensure_container_image` build-context argument.
  Its runtime install command is left alone.
- `.containerignore` — new file at the project root.
- No `src/` change. No change to the project's declared dependencies, the
  lockfile, or any published behaviour of the plugin.
- Developers holding a cached `aiida-slurm-test:latest` image get a rebuild on
  next run, because the Dockerfile text changes.
