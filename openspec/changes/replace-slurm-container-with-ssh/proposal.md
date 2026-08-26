# Replace the Slurm container with an SSH-only integration test

> **Status: proposal only.** Recorded so the investigation behind it is not
> lost. `specs/`, `design.md` and `tasks.md` are not yet written, so this change
> does not validate. See "Open questions" before continuing.

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

The scheduler is not abandoned: peace of mind that scheduled computers behave
the same moves to a human-run tutorial, where it is more useful to users anyway,
because anyone on real HPC must configure their own computer regardless.

## What Changes

- **Delete** `tests/container/` and `tests/slurm_support.py` and rebuild rather
  than repair. The current image carries debugging residue, duplicated setup and
  a committed private key; a replacement is smaller than the diff to fix it.
- Build the image around an SSH daemon and a Python environment only. No munge,
  no `slurmctld`/`slurmd`, no `slurm.conf`, no node state management.
- Configure the AiiDA `Computer` with `core.ssh` transport and `core.direct`
  scheduler.
- Provision the remote environment with a plain, non-editable install of the
  project, so dependency resolution is the one users are told to rely on and the
  built distribution is exercised. The present editable install into a read-only
  mount tests neither.
- Generate the SSH keypair per session with aiida-core's `ssh_key` fixture and
  inject the public key at run time, removing the committed private key from the
  repository and making the image generic. Note that only `ssh_key` is useful
  here: the sibling `aiida_computer_ssh` factory accepts nothing but a label and
  a configure flag, hard-codes `localhost`, and cannot express a port or
  username, so it cannot address a container. Its docstring also claims the key
  is added to the user's authorised keys, which nothing in aiida-core does. The
  `Computer` is therefore constructed explicitly, which is also better material
  for the documentation that will include it.
- Split fixture state by kind: session-scoped connection details that survive
  database resets, function-scoped ORM nodes that are cheap to recreate.
- Replace the single opaque readiness poll with named, separately-reported
  stages, and separate provisioning from readiness.
- Let the container engine assign the published port and read it back, instead
  of choosing one in Python beforehand — which is also what the current spec
  already describes.

## Capabilities

### Modified Capabilities

- `testing-and-ci`: the three containerized-integration requirements are
  rewritten. The scheduler is no longer part of the contract; the container's
  purpose becomes exercising remote execution over SSH against an interpreter
  that has no AiiDA.

## Non-goals

- **Slurm coverage in the test suite.** It moves to a human-run tutorial in
  `document-ssh-pythonjob-computers`.
- **A queueing scheduler.** `core.direct` is sufficient because the suite runs
  serially. HyperQueue, via the `aiida-hyperqueue` plugin, is a recorded
  deferred upgrade: a single static binary needing no root or munge, which would
  restore both real queueing and the asynchronous submit/poll/retrieve lifecycle
  that `core.direct` lacks. Revisit if contention or lifecycle coverage becomes
  a real gap.
- **Committing to an upstream base image.** For a plain SSH box the question is
  small enough to settle during implementation.
- **Making the fixture runnable in a sandboxed development container.** It
  cannot be, for reasons outside this repository; see
  `add-container-fixture-cli`.

## Impact

- `tests/container/`, `tests/slurm_support.py`, `tests/test_remote_slurm.py`,
  `tests/conftest.py` fixtures, and the `testing-and-ci` spec.
- Removes a committed private key from version control.
- No source module, dependency, entry point or public API is touched.

## Open questions

- Which base image, and how much to build ourselves. Smaller than before, since
  an sshd container is auditable in a few lines.
- Whether any scheduler coverage should remain in the suite at all, or move
  entirely to the tutorial.
- Whether the SSH-only container subsumes `add-lean-remote-env-test`. It does
  not: that runs where no container engine exists, which includes sandboxed
  development environments.
