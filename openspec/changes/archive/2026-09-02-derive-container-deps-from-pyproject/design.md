## Context

See proposal.md — Why. The design-relevant constraints, each established by
inspection or by trial rather than assumed:

- The image is built by `ensure_container_image` with `tests/container/` as the
  build context, so `pyproject.toml` lies outside it and no `COPY` can reach
  it. Docker and Podman both refuse paths above the context root.
- Container layer caching keys a `RUN` layer on the literal command text and a
  `COPY` layer on the content of the files copied — not on the size or contents
  of the wider build context. `COPY pyproject.toml` followed by an install
  therefore re-executes exactly when `pyproject.toml` changes.
- The build context *is* tarred and transferred in full on every build. The
  project root is 526 MB, of which `.venv/` is 502 MB and the generated
  `docs/build/` a further 9.6 MB. No `.containerignore` or `.dockerignore`
  exists today. Context size and image size are independent: nothing in the
  context reaches the image except what a `COPY` names, so context exclusions
  buy build time, not image bytes.
- The image's bulk is the Python environment. Measured from equivalent local
  installs: the full runtime set is ~500 MB, of which `scipy` (93 MB), `numpy`
  (34 MB) and their bundled `.libs` (58 MB) are an irreducible ~185 MB that
  Euphonic requires. uv's wheel cache for a comparable set measures 221 MB.
- The apt layer installs `sudo`, which nothing in `tests/container/` or
  `tests/slurm_support.py` ever invokes, and `python3-pip` / `python3-venv`,
  which exist only to bootstrap uv. `uv venv --python 3.12` on Ubuntu 22.04
  (which ships Python 3.10) already downloads a uv-managed CPython, so the
  system interpreter never backs the job environment.
- `pyproject.toml` sets `[tool.uv] find-links = ["wheels"]` unconditionally, to
  serve the vendored aarch64 Euphonic wheel. uv aborts when that directory is
  missing, even on x86-64 where it holds only `.gitkeep`:
  `error: Failed to read --find-links directory: .../wheels`.
- `uv pip install -r pyproject.toml` reads a project's `[project.dependencies]`
  directly. Verified against this project: 111 packages, `abinslib==0.2.0`,
  `aiida-core==2.9.1`, `euphonic==2.0.0`, `resins==0.1.0` — the same set the
  hand-written list produces, with the abinslib version corrected. Dependency
  groups are excluded, matching the current image.
- The fixture installs the project at container start with
  `uv pip install --python /home/ubuntu/venv -e /workspace`, against a read-only
  bind mount. `--no-deps` was removed by `a37f5e0`, so this now re-resolves the
  full dependency set on every session and reconciles whatever the image holds.
  The baked layer is consequently a warm cache rather than the sole source of
  the container's dependencies — which is why the acute breakage is already
  fixed while the duplicate list survives.
- `aiida-pythonjob` pickles job functions by reference unless
  `register_pickle_by_value` is set, which this project does not set
  (`aiida_pythonjob/utils.py`; see also the "Remote Execution, Pickling, and
  register_pickle_by_value" note in `docs/source/design_notes.rst`). The
  payload is a module path, so unpickling runs `operations.py`'s module-level
  imports on the remote. This is why a dependency mismatch in the image
  presents as a failure of *every* remote job rather than of the jobs that use
  the changed interface.

## Goals / Non-Goals

**Goals:**

- One statement of each dependency version, in `pyproject.toml`.
- Keep the dependencies baked into the image. Container start must not need a
  dependency resolution or a network round-trip.
- Invalidate the image exactly when the declared dependencies change, and not
  otherwise.
- Ship neither files nor packages the build does not need, and make the
  reduction measurable rather than asserted.

**Non-Goals:**

- Changing which *project dependencies* the image holds. Installing from
  `pyproject.toml` reproduces today's set, `aiida-core` included. Dropping the
  AiiDA stack is worth roughly 285 MB (a no-AiiDA environment of
  `euphonic[phonopy-reader]`, `seekpath`, `abinslib`, `resins` and `cloudpickle`
  measures 216 MB against ~500 MB for the full set), but it changes what is
  being tested and belongs to `replace-slurm-container-with-ssh`. Recorded here
  with a number so that change can be argued on evidence.
- Guaranteeing the container and host resolve to identical versions. See
  Decision 2 — that is rejected, not merely out of scope.

## Decisions

### Decision 1: Move the build context to the project root rather than copying the manifest into `tests/container/`

`ensure_container_image` passes the project root as the context and
`tests/container/Dockerfile` as an explicit `-f` argument. The three existing
`COPY` sources become `tests/container/`-relative.

- **Rationale**: `pyproject.toml` must be inside the context to be copied, and
  it cannot move. The alternative is to bring a copy to the manifest instead of
  the manifest to the copy, which reintroduces the duplicate this change exists
  to remove.
- **Alternatives considered**:
  - *Generate the dependency list into `tests/container/` from `pyproject.toml`
    as a build step*: keeps the small context, but the generated file is a
    second copy that is correct only as long as someone regenerates it. A
    committed generated artefact drifts the same way a hand-written one does,
    and a generated-but-uncommitted one has to run before every build, which is
    the context move with extra machinery.
  - *Symlink `pyproject.toml` into `tests/container/`*: build contexts do not
    follow symlinks out of the context root; the link is copied as a link and
    dangles.

### Decision 2: Install from `pyproject.toml`, giving constraint parity, not from `uv.lock`

`COPY pyproject.toml` and `COPY wheels/`, then
`uv pip install --python /home/ubuntu/venv -r pyproject.toml`.

Lockfile parity is achievable and was tested: with `pyproject.toml` and
`uv.lock` alone in a directory, `uv export --frozen --no-dev --no-emit-project`
produces a fully hashed requirements file, which installs to exactly the host's
resolution.

- **Rationale**: The container stands in for a compute node, and a compute node
  will not have this project's lockfile. Resolving independently from the
  declared constraints is what a real deployment does, so it is what the
  integration test should do. It also gives the constraints themselves some
  coverage: a range that admits a broken combination can surface here, whereas
  under lockfile parity the container can only ever confirm that the host's
  single known-good resolution works, which the host already demonstrates.
- **Alternatives considered**:
  - *Export `uv.lock`*: reproducible and hermetic, and the better choice if the
    container's job were to isolate this project's changes from upstream
    releases. It is not — that is CI's job on the host legs. It also makes the
    remote a clone of the submitting side, weakening the one property this
    fixture is uniquely placed to test, and it sits awkwardly with
    `scope-ci-container-testing`'s interest in a remote that deliberately
    differs from the host.
  - *Keep the pinned list and add a parity assertion*: detects drift instead of
    preventing it, and still requires the manual edit that was missed here.
- **Observed in practice**: the first build under this decision resolved
  `aiida-core 2.9.1` while the host lockfile holds `2.8.1`. Nothing caps it —
  the project declares `>=2.6,<3` and `aiida-pythonjob` requires `>=2.7.1`, so
  the lock is simply older than the release. The other five direct dependencies
  matched the host exactly (`abinslib 0.2.0`, `aiida-pythonjob 0.5.2`,
  `euphonic 2.0.0`, `resins 0.1.0`, `seekpath 2.2.1`). This is the decision
  behaving as intended rather than a fault, and small compatible discrepancies
  are what the declared ranges exist to permit.
- **Consequence to keep in mind**: the containerized tests become the only leg
  exercising a version the rest of the suite does not. A genuine upstream
  incompatibility will therefore surface only there, and will present as a
  container failure. That is useful early warning, but when those tests fail the
  first question is which aiida-core they ran, not what changed in this
  repository.

### Decision 3: Make `.containerignore` an allowlist, not a denylist

```
*
!pyproject.toml
!wheels
!tests
tests/*
!tests/container
```

- **Rationale**: A denylist has to be maintained, and this change exists
  precisely because a hand-maintained list rotted. Measured on this tree, the
  build needs 32 KB (`pyproject.toml` 12 KB, `wheels/` empty, `tests/container/`
  20 KB); the unfiltered root is 526 MB; a denylist naming `.venv/`,
  `docs/build/`, `.git/` and the caches still leaves 6.8 MB, dominated by
  `tests/data/` (3.0 MB), `docs/source/` (2.2 MB), `uv.lock` (652 KB) and
  `openspec/` (632 KB). None of that is needed, and a future generated
  directory would silently join it. Under an allowlist nothing can be added to
  the context by accident, because inclusion is enumerated rather than inferred.
  `containerignore(5)` documents this form explicitly: "you may want to specify
  which files to include in the context, rather than which to exclude. To
  achieve this, specify `*` as the first pattern, followed by one or more `!`
  exception patterns", with last-matching-line-wins precedence. Podman reads
  `.containerignore` in preference to `.dockerignore` and falls back to the
  latter, so one file serves both engines.
- **Verified** against podman 4.3.1 on a 395 MB synthetic tree of the same
  shape, using a `FROM scratch` + `COPY . /ctx` probe: the resulting image was
  10.2 KB and contained exactly `pyproject.toml`, `wheels/.gitkeep` and the four
  files under `tests/container/`. `.venv/`, `docs/`, `src/`, `openspec/`,
  `uv.lock` and `tests/data/` were all absent.
- **On the redundant-looking middle lines**: `*` uses Go's `filepath.Match`, so
  it matches top-level names only and prunes their subtrees; `!tests` /
  `tests/*` / `!tests/container` walks down to the wanted directory one level at
  a time. The shorter `*` + `!tests/container` also worked under podman 4.3.1,
  but nested re-inclusion is a long-standing source of engine-specific surprise
  (moby#43232, moby#42788, docker/cli#2919) and CI builds with Docker, not
  podman. The level-by-level form costs two lines and avoids betting on
  cross-engine agreement.
- **Alternatives considered**:
  - *Denylist the known-large directories*: what this change originally
    proposed. Smaller diff, but leaves 200x more context than needed and
    reintroduces exactly the maintenance burden being removed.
  - *Rely on the layer cache to make context size irrelevant*: the cache is
    consulted only after the context is transferred, so the cost is paid on
    every build including no-op ones.

### Decision 4: Leave the fixture's runtime install as it is; defer `--no-deps`

`a37f5e0` removed `--no-deps`, and this change does not put it back. The fixture
continues to run `uv pip install --python /home/ubuntu/venv -e /workspace`.

- **Rationale**: Restoring the flag is an optimisation, not a correctness fix,
  and its value rests entirely on the cache-invalidation argument in Decision 1
  holding in practice. That argument has not yet been observed against a real
  build — no image could be built in the development sandbox (see the note at
  the foot of tasks.md) — so the saving is projected rather than measured, while
  the reconciliation it would remove is currently what keeps the container
  correct. Removing a working safeguard to buy an unmeasured saving is the wrong
  order of operations. Keeping it also holds this change to one subject:
  deleting the duplicate dependency list.
- **Consequence, stated plainly**: the container then has two mechanisms
  reaching the same result — a baked layer derived from `pyproject.toml` and a
  runtime resolution from the same file. That redundancy is accepted for now.
  It costs a full resolution (~111 packages) and a network dependency at every
  container start, and it means the baked layer's correctness is not actually
  load-bearing, so a regression in it would be masked rather than reported.
- **Revisit when**: the invalidation behaviour has been observed on a real build
  (tasks 5.5) and the per-session cost of the runtime resolution has been timed.
  If the saving is material and invalidation behaves, restore `--no-deps` and
  pair it with `uv pip check --python /home/ubuntu/venv`, which reads installed
  metadata only, needs no network, and was confirmed to catch exactly this
  change's motivating drift: against `abinslib 0.1.0.post1` it reports `The
  package aiida-pythonjob-ins requires abinslib~=0.2.0, but 0.1.0.post1 is
  installed` and exits 1. That pairing is the intended end state; it is simply
  not this change.
- **Alternatives considered**:
  - *Restore `--no-deps` now*: removes the redundancy and the per-session cost,
    and makes the baked layer load-bearing so that a fault in it is reported
    rather than absorbed. Rejected on sequencing — it reverses a deliberate fix
    made days ago on evidence this change cannot yet supply.
  - *Restore `--no-deps` and add `uv pip check` in this change*: the strongest
    end state, and cheap. Still rejected for now, because the check's value is
    to catch a stale baked layer, and while the runtime resolution stands there
    is no stale layer for it to catch.

### Decision 5: Cut the image to what the build needs, in two low-risk moves

Both stay inside this change because both are edits to the same install steps
the dependency work already rewrites.

1. **Install with `uv pip install --no-cache`.** uv's wheel cache is written
   during the install and has no use afterwards in a single-purpose image. Its
   cost in the image depends on whether uv's hardlinks into the venv survive as
   hardlinks in the layer tar, which is why this is measured rather than
   claimed — see Decision 6.
2. **Drop `sudo`, `python3-pip` and `python3-venv` from the apt layer**, and
   obtain uv from its published image with
   `COPY --from=ghcr.io/astral-sh/uv:<pinned> /uv /usr/local/bin/uv` instead of
   `pip install uv`. `sudo` is dead weight — nothing invokes it. The other two
   exist only to bootstrap uv, and `COPY --from` removes that need entirely
   while adding only a static binary. `python3` itself is kept: it is cheap,
   and apt would pull it back for `slurm-wlm` regardless.

- **Measured, and already implemented**: both moves were applied and built. The
  image went from **1.28 GB to 824 MB, a saving of 456 MB (36%)** — larger than
  the ~270 MB projected from local cache and virtualenv sizes. The baseline
  build reproduced the existing `aiida-slurm-test:latest` image ID exactly, so
  the comparison is like for like, and `pytest -m containerized` passes against
  the reduced image, which is what establishes that the removed apt packages
  were genuinely unused.
- **Rationale**: These are the reductions available without changing what the
  container tests. Everything larger is a dependency question, not a packaging
  one, and is excluded under Goals / Non-Goals. At 824 MB the remaining bulk is
  roughly: the virtualenv ~500 MB, uv's managed CPython ~130 MB, base image plus
  slurm/munge/sshd ~150 MB, the uv binary ~35 MB. The only large reducible item
  left is the AiiDA stack (~285 MB), which is out of scope by Goals / Non-Goals.
- **Alternatives considered**:
  - *`uv cache clean` as a final step in the same `RUN`*: equivalent in effect
    but relies on the cleanup being kept in the same layer as the install; a
    later refactor that splits the `RUN` would silently restore the cache.
    `--no-cache` cannot be defeated that way.
  - *A multi-stage build copying only the finished venv*: a larger saving in
    principle, but the venv holds absolute interpreter paths and a uv-managed
    CPython outside it, so it does not relocate cleanly. Not worth the fragility
    for a test fixture.
  - *A slimmer base than `ubuntu:22.04`*: `slurm-wlm` and `munge` are packaged
    for Debian/Ubuntu, and sourcing them elsewhere is a much larger change than
    this one.

### Decision 6: Prove the reduction by measurement, against a recorded baseline

The change is not complete on inspection. Record `podman image inspect --format
'{{.Size}}'` for the image built from the pre-change Dockerfile, then for the
image built after, and report both.

- **Result**: 1.28 GB before, 824 MB after; −456 MB. Recorded in Decision 5.
- **Rationale**: Every estimate in this document was derived from local
  virtualenv sizes and a cache measurement, not from a built image, and the
  projection was low by ~185 MB — which is the argument for measuring rather
  than asserting. A task that says "reduce the image" without a number cannot be
  checked off honestly.
- **Still open**: the saving has not been attributed between the two moves.
  `podman history` on both images would separate "python3-pip and its
  dependencies were fatter than expected" from "uv's cache was not
  hardlink-deduplicated within the layer". Worth knowing, since only the second
  generalises to other images, but not worth blocking on.
- **Context-size verification uses the same idea**: neither podman nor docker
  reports context size directly, so measure it with a throwaway `FROM scratch` +
  `COPY . /ctx` probe and inspect the resulting image size. This was the method
  used to verify Decision 3 and is known to work.

### Decision 7: The `ruff format` violation is already fixed — no longer in scope

**Completed by `4dd6687` before this change was written.** Recorded because the
reasoning still explains why the repository was in that state, and why a fix was
needed before anything here could be shown green.

- **Why it mattered**: The CI `test` job declares `needs: lint`, and `ruff
  format --check` failed on `tests/slurm_support.py`, so the suite did not run in
  CI at all — nothing here could have been shown green while that stood.
  Established as pre-existing rather than fallout from the dependency bump: the
  file was untouched by the rebase and ruff is 0.16.0 in both lockfiles.
- **Current state**: `uv run ruff check` and `uv run ruff format --check` both
  pass (115 files formatted, no lint findings), so the CI `lint` gate is open.

## Risks / Trade-offs

- **The container's resolution can drift from the host's over time**, since
  ranges float. A dependency could release a version that breaks the remote
  while the host's lockfile holds it back, and the containerized tests would be
  the only place it appears. → This is Decision 2 working as intended rather
  than a defect; the failure it produces is the signal. The cost is that the
  containerized tests can fail for reasons unrelated to the commit under test,
  which is already true of any unpinned integration environment.
- **A new file the build genuinely needs will be missing from the context**,
  because the allowlist excludes by default. → The failure is immediate and
  legible (`COPY` fails on a missing path at build time), which is the right way
  round: the denylist's failure mode was silent inclusion of 6.8 MB that nobody
  noticed, and before that, silent staleness that nobody noticed.
- **Nested re-inclusion could behave differently under Docker than podman.**
  CI builds with Docker; Decision 3 was verified only against podman 4.3.1. →
  Mitigated by using the conservative level-by-level form rather than the short
  one, and by task 1.1 measuring the context on both engines available to the
  implementer.
- **`COPY --from` on a published uv image adds an external dependency to the
  build**, and an unpinned tag would drift. → Pin the tag. The alternative,
  `pip install uv`, is also an external dependency and an unpinned one; this
  swaps an implicit floating dependency for an explicit pinned one.
- **Dropping `python3-pip` / `python3-venv` could break something that used them
  implicitly.** → Nothing in `tests/container/` invokes `pip` or `venv`, and the
  job environment is a uv-managed CPython. If apt needs them for `slurm-wlm`
  they return automatically as dependencies. The containerized tests are the
  check.
- **Cold rebuild cost moves onto whoever next changes a dependency.** The full
  dependency install is a multi-minute layer. → Correct attribution: they are
  the person who needs the new environment. Previously they got a fast build of
  a wrong environment.
- **The build context enlargement is engine-visible.** Some CI cache actions key
  on context contents. → This project's CI does not cache the image; it builds
  fresh on each leg.
- **`COPY wheels/` bakes the aarch64 wheel directory into an x86-64 image**,
  where it is empty but for `.gitkeep`. → Harmless, and required by the
  unconditional `find-links`. The alternative, making `find-links` conditional
  in `pyproject.toml`, changes the project's declared configuration to suit a
  test fixture and is the wrong direction.

## Migration Plan

No deployment or data migration. Developers holding a cached
`aiida-slurm-test:latest` receive a rebuild automatically, because the
Dockerfile text changes; no manual `image rm` is needed. Rollback is a revert of
the three touched files.
