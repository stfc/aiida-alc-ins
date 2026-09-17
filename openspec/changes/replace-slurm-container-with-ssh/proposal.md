# Replace the Slurm container with a lightweight SSH and HyperQueue test environment

> **Status: proposal and design in progress.** Recorded so the investigation behind it is not
> lost. `specs/` and `tasks.md` are not yet written, so this change does not yet validate.

## Why

The existing containerized test welds three separable concerns into one
fixture — a foreign interpreter, an SSH transport, and a Slurm scheduler — and
that fusion is what made it expensive to build and expensive to keep working.
Only the first two exercise anything this package is responsible for.

Established by investigation, so it need not be re-derived:

- **This package has no scheduler-facing surface.** No `metadata.options`,
  `resources`, `num_machines`, `withmpi`, `queue_name`, `max_wallclock_seconds`
  or `custom_scheduler_commands` appears anywhere in `src/`. Input builders take
  `computer` and `code` and forward `**kwargs`. There is no code here that can
  be wrong about Slurm specifically; `core.slurm` is aiida-core's plugin and
  aiida-core tests it.
- **The remote side needs no AiiDA.** The script `aiida-pythonjob` generates
  imports only `sys`, `json`, `traceback`, `cloudpickle`, plus `node_graph` and,
  when MPI is requested, `mpi4py`. Confirmed by running a real `PythonJob` in an
  environment containing neither `aiida-core` nor `aiida-pythonjob`. The current
  container installs both, which is not merely wasteful: with AiiDA present on
  the remote, a leak of `import aiida` into the operations chain still passes,
  so the fat environment defeats the test's own purpose.
- **The image recommended by the archived design is unusable** — Ubuntu 16.04,
  Python 3.5.2, Slurm 17.02.6, last published 2020 — which is why a custom image
  was built instead. Anonymous pulls from GHCR do work for other `aiidateam`
  packages; only `slurm-image` is inaccessible.
- **Dropping Slurm collapses the fixture's failure surface** from four
  interacting readiness conditions to one, which is the single largest
  contributor to the original debugging cost.
- **HyperQueue provides realistic queuing without daemon overhead.** Unlike
  `core.direct` (which runs unmanaged background processes with no queue states
  or slot limits), HyperQueue (`aiida-hyperqueue`) provides a true modern task
  scheduler via a single static, unprivileged binary (`hq`). It restores realistic
  submit/queue/poll/retrieve lifecycle testing with zero system daemons, no root
  requirements, and no munge authentication.
- **Parallel test runners can share the HyperQueue instance.** Workflow tests
  are mostly blocking event loops waiting on sequential steps. Parallel pytest
  workers (`pytest-xdist`) submitting independent workflow tests to a shared
  HyperQueue container interleave execution across available worker slots for
  efficient test concurrency.

The Slurm scheduler is not abandoned: peace of mind that scheduled computers
behave the same moves to a human-run tutorial, where it is more useful to users
anyway, because anyone on real HPC must configure their own computer regardless.

## What Changes

- **Delete** `tests/container/` and `tests/slurm_support.py` and rebuild rather
  than repair. The current image carries debugging residue, duplicated setup and
  a committed private key; a replacement is smaller than the diff to fix it.
- Build a minimal container image around an SSH daemon, a static `hq` binary,
  and a clean Python virtual environment. No munge, no `slurmctld`/`slurmd`,
  no `slurm.conf`, no root daemon requirements.
- Configure the container entrypoint to start `hq server` and `hq worker` as an
  unprivileged user, and run `sshd`.
- Configure the AiiDA `Computer` with `core.ssh` transport and `hyperqueue`
  scheduler (via the `aiida-hyperqueue` plugin).
- Provision the remote environment with a plain, non-editable install of the
  project, so dependency resolution is the one users are told to rely on and the
  built distribution is exercised.
- Generate the SSH keypair per session with aiida-core's `ssh_key` fixture and
  inject the public key at run time, removing the committed private key from the
  repository and making the image generic.
- Support parallel test execution via `pytest-xdist`:
  - Adopt the official `pytest-xdist` `FileLock` pattern in `tests/conftest.py`
    to ensure the container is launched lazily and shared across all xdist
    workers.
  - Add test collection ordering (`pytest_collection_modifyitems`) so fast unit
    tests execute first at full speed without waiting for container boot,
    starting the container only when workers reach integration tests.
  - Coordinate single teardown on the controller process via `pytest_sessionfinish`.
- Let the container engine assign the published port dynamically and read it back,
  preventing port collisions across parallel workers.
- Add `aiida-hyperqueue`, `pytest-xdist`, and `filelock` to `[dependency-groups].dev`
  in `pyproject.toml`.

## Capabilities

### Modified Capabilities

- `testing-and-ci`: the three containerized-integration requirements are
  rewritten. The scheduler is HyperQueue; the container exercises remote
  execution over SSH against an interpreter that has no AiiDA; and the
  fixtures are process-safe under `pytest-xdist`.

## Non-goals

- **Slurm coverage in the test suite.** It moves to a human-run tutorial in
  `document-ssh-pythonjob-computers`.
- **Making the fixture runnable in a sandboxed development container.** It
  cannot be, for reasons outside this repository; see
  `add-container-fixture-cli`. Local development continues to rely on
  `pytest -m venv_code` for AiiDA-free interpreter verification.

## Impact

- `tests/container/`, `tests/slurm_support.py` (replaced with `tests/container_support.py`),
  `tests/test_remote_slurm.py` (renamed to `tests/test_remote_ssh.py`),
  `tests/conftest.py` fixtures, and the `testing-and-ci` spec.
- `pyproject.toml`: adds `aiida-hyperqueue`, `pytest-xdist`, and `filelock` to `dev` group.
- Removes a committed private key from version control.
- No source module, runtime dependency, entry point or public API is touched.

## Open questions

- Base image choice for the container (Ubuntu 22.04 minimal vs Debian bookworm-slim).
- Core slot count allocated to the containerized `hq worker` (auto-detect vs explicit 2 cores).
