## 1. Correct the record

- [x] 1.1 Add a superseded pointer to the top of
  `openspec/changes/archive/2026-08-25-add-slurm-integration-tests/proposal.md`,
  `design.md` and `tasks.md`, naming the inaccurate claims (the recommended base
  image, in-memory key generation, the remote install step, and engine-assigned
  port allocation) and pointing at this change; verify by reading each file back
  and confirming the body below the pointer is unedited against `git diff`.
- [x] 1.2 Correct the `slurm_container` fixture docstring in `tests/conftest.py`
  so it names the locally built image rather than `ghcr.io/aiidateam/slurm-image`;
  verify with `grep -rn "ghcr.io" tests/` returning no matches.
- [x] 1.3 Record the registry findings in the pointer added in 1.1: anonymous
  GHCR pulls succeed for other `aiidateam` packages while `slurm-image` returns
  403, and the archived design's recommended Docker Hub image is an Ubuntu 16.04
  build carrying Python 3.5 and Slurm 17.02. Verify the statements are present
  and attributed as measurements, not assertions.

## 2. Remove vestigial code

- [x] 2.1 Delete `discover_container_port()` from `tests/slurm_support.py`;
  verify with `grep -rn discover_container_port` returning no matches and
  `uv run ruff check` passing.
- [x] 2.2 Delete the `MEMORY` computation and its `sed` substitution from
  `tests/container/entrypoint.sh`; verify with
  `grep -c MEMORY tests/container/entrypoint.sh tests/container/slurm.conf`
  reporting zero for both.
- [x] 2.3 Remove `set -x` from `tests/container/entrypoint.sh` and the
  `chown`/`chmod` lines already applied at image build time; verify the script
  still passes `bash -n tests/container/entrypoint.sh`.
- [x] 2.4 Delete `tests/container/cgroup.conf` and its `COPY` line in
  `tests/container/Dockerfile`; verify with `grep -rn cgroup tests/container/`
  returning no matches.
- [x] 2.5 Remove `LogLevel DEBUG` from the `sshd_config` generated in
  `tests/container/Dockerfile` and the duplicated ownership fix-ups in image
  step 5; verify with `grep -n "LogLevel" tests/container/Dockerfile` returning
  no matches.

## 3. Verification

- [x] 3.1 Confirm no source module, dependency, entry point or public API was
  touched: `git diff --name-only` lists only files under `tests/` and
  `openspec/changes/archive/`.
- [x] 3.2 Run `uv run pytest -m "not containerized"` and `uv run ruff check`
  and confirm both pass with the same results as before the change.
- [x] 3.3 Run the containerized tests on a machine with a working container
  engine (or in CI) and confirm they still pass, since the deletions touch the
  image build and entrypoint.
