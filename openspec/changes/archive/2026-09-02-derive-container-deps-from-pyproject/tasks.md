## 1. Baseline measurements

Take these before changing anything; later tasks compare against them.

- [x] 1.1 Build the current Dockerfile unchanged and record the image size —
  **done: 1.28 GB**. The baseline build reproduced the existing
  `aiida-slurm-test:latest` image ID exactly, confirming it is the real current
  image and not a variant
- [x] 1.2 Record the current build-context size with a `FROM scratch` +
  `COPY . /ctx` probe — **done**; `tests/container/` measures ~20 KB, the
  reference the project-root context in 2.2 must not regress

## 2. Build context

- [x] 2.1 Add `.containerignore` at the project root as an allowlist per design
  Decision 3: `*`, then `!pyproject.toml`, `!wheels`, `!tests`, `tests/*`,
  `!tests/container`
- [x] 2.2 Re-run the 1.2 probe with the project root as context — **done:
  25.0 KB** (from an unfiltered 526 MB), containing exactly `pyproject.toml`,
  `wheels/.gitkeep` and the five files under `tests/container/`, with nothing
  from `.venv/`, `docs/`, `src/`, `openspec/`, `uv.lock` or `tests/data/`
- [x] 2.3 Change `ensure_container_image` in `tests/slurm_support.py` to build
  with the project root as context and `-f tests/container/Dockerfile`; verify
  the build succeeds from a clean cache (`podman image rm -f
  aiida-slurm-test:latest` first)
- [x] 2.4 Update the `COPY` sources for `id_rsa.pub`, `slurm.conf` and
  `entrypoint.sh` to their `tests/container/`-relative paths; verify the build
  reaches completion rather than failing on a missing context path

## 3. Dependency source

- [x] 3.1 `COPY pyproject.toml` and `COPY wheels/` into the image ahead of the
  dependency install, placing them where the `ubuntu` user can read them;
  verify the copied `wheels/` exists in the image so uv does not abort with
  `Failed to read --find-links directory`
- [x] 3.2 Replace the hard-coded package list in the Dockerfile's
  `uv pip install` with `-r pyproject.toml`; verify no version or version
  constraint for a project runtime dependency remains anywhere in
  `tests/container/Dockerfile` (satisfies the spec scenario "The declared
  dependencies are the only place a version is stated")
- [x] 3.3 Verify the resulting image resolves the same package set as before
  with the abinslib version corrected — **done**: `abinslib 0.2.0`,
  `aiida-core 2.9.1`, `aiida-pythonjob 0.5.2`, `euphonic 2.0.0`, `resins 0.1.0`,
  `seekpath 2.2.1`. Five of six match the host lockfile; `aiida-core` floats one
  minor ahead of the lock's `2.8.1`, which is constraint parity working as
  designed (design Decision 2, "Observed in practice")
- [x] 3.4 Leave the fixture's runtime `uv pip install ... -e /workspace`
  untouched, per design Decision 4 — `--no-deps` stays off. Verify by diffing
  `tests/slurm_support.py` at the end of the change: the only edit to it should
  be the build-context argument from 2.3

## 4. Image size

**This group is already implemented and verified** — do not redo it. The edits
are present in `tests/container/Dockerfile`; confirm they survive the changes in
groups 2 and 3 rather than reapplying them.

- [x] 4.1 Add `--no-cache` to the Dockerfile's `uv venv` and `uv pip install`
  so uv's wheel cache does not land in the layer
- [x] 4.2 Remove `sudo`, `python3-pip` and `python3-venv` from the apt install
  list, add `ca-certificates` explicitly, and obtain uv via
  `COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv`
- [x] 4.3 Verify nothing depended on the removed packages — `pytest -m
  containerized` passes against the reduced image, which exercises sshd, munge
  and slurm end to end
- [ ] 4.4 Optional, not blocking: attribute the saving between 4.1 and 4.2 with
  `podman history --human` on both images, and record whether uv's cache was
  hardlink-deduplicated within the layer (design Decision 6, "Still open")

## 5. Verification

- [x] 5.1 Clear the `ruff format` violation in `tests/slurm_support.py` that was
  gating the CI `test` job — **done in `4dd6687`**, before this change was
  written; `uv run ruff check` and `uv run ruff format --check` both pass
- [x] 5.2 Re-run `uv run ruff check` and `uv run ruff format --check` after the
  edits above; verify they still pass
- [x] 5.3 Compare the rebuilt image against the 1.1 baseline — **done:
  1.28 GB → 824 MB, −456 MB (36%)**, recorded in design Decisions 5 and 6
- [x] 5.3a Re-measure once groups 2 and 3 are implemented — **done: 824 MB**,
  unchanged from the pre-dependency-source measurement, confirming that
  installing from `pyproject.toml` resolves the same package set as the
  hard-coded list did
- [x] 5.4 Run `uv run pytest -m "not containerized"`; verify the 70
  non-container tests still pass, confirming no collateral change
- [x] 5.5 On a machine with a working container engine, run
  `uv run pytest -m containerized` — **done, all three pass** against the
  completed change (build-context move, `COPY pyproject.toml` as dependency
  source, and the `cd /tmp/deps` find-links fix), with `aiida-core 2.9.1`
  resolved in the container against `2.8.1` on the host. Note that they
  pass on `main` already — `a37f5e0` fixed the acute breakage — so this is a
  no-regression check, not a demonstration that the change works. What it must
  confirm is that they still pass once the dependency list comes from
  `pyproject.toml` (satisfies the spec scenario "A job function importing a
  changed dependency runs remotely")
- [x] 5.6 **Required, done — both directions confirmed.** The dependency layer
  invalidates when the manifest changes, and not when the fixture's own config
  files do. Cache keys
  come from the *content of files a `COPY` names*, not from context membership,
  so the two checks that mean anything are:
  - *Invalidates when it must* — **done**: a trivial change to `pyproject.toml`
    followed by `podman build` re-ran both the `COPY` and the Python package
    install. This is the mechanism that replaces the hand-maintained list, and
    it is the claim the whole change rests on.
  - *Layer ordering is right* — **done**: editing
    `tests/container/entrypoint.sh` left the dependency install served from
    cache. The three fixture files (`id_rsa.pub`, `slurm.conf`,
    `entrypoint.sh`) are copied *after* the dependency install precisely so
    that editing them is cheap; had any been placed above it, every tweak to
    the Slurm config would trigger a full reinstall.

  Together these are the spec scenarios "A declared dependency constraint is
  changed" and "An environment-only change is not silently ignored", so the
  change is not honestly complete without them.
- [ ] 5.7 **Optional; does not gate this change.** Time the fixture's runtime
  `uv pip install ... -e /workspace` on a warm image. This verifies nothing — it
  collects the one number design Decision 4 needs before the deferred
  `--no-deps` question can be reopened, namely what a full dependency resolution
  costs per container start. Seconds means leave it alone; tens of seconds on
  every containerized session means the follow-up is worth scheduling. Can be
  done at any time, including after this change is archived
- [x] 5.8 Run `openspec validate derive-container-deps-from-pyproject --strict`;
  verify it reports no errors

## Note on running these in the dev sandbox

Tasks 1.1, 4.x and 5.2 need an engine that can unpack a normal base image.
Rootless podman inside this sandbox cannot: the outer container runs with
`--userns=keep-id`, so a single UID is available and applying the `ubuntu:22.04`
layer fails with `potentially insufficient UIDs or GIDs available in user
namespace (requested 0:42 for /etc/gshadow)`. `ignore_chown_errors` would solve
it but needs the `overlay` driver with `fuse-overlayfs`, and `/dev/fuse` is not
exposed to the sandbox. Either run these on the host, or relaunch the sandbox
with `--device /dev/fuse`. Context-only checks (1.2, 2.2) do work in the
sandbox, because a `FROM scratch` probe unpacks no base layer.
