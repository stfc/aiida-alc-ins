## Context

See `proposal.md` for motivation. The relevant constraint here is that every
deletion must be justified by evidence rather than by inspection, because the
container fixture is difficult to run (it needs a container engine, and a
nested rootless engine cannot accept SSH logins — see Risks) and a mistaken
deletion would surface only in CI. This document records the evidence for each
removal so a reviewer does not have to re-derive it, and fixes the boundary
against the still-exploratory container rework.

## Goals / Non-Goals

**Goals:**

- Leave behind a record of *why* each deleted item is dead, not merely that it
  was deleted.
- Correct the archived change without rewriting it, so the original reasoning
  stays legible as history.
- Keep the change reviewable as pure subtraction plus prose: no reviewer should
  need to reason about behaviour.

**Non-Goals:**

- Deciding anything about the container's future shape. Where a fix would
  require a behaviour change (the committed key, the port strategy), this
  design deliberately records the deferral rather than the fix.

## Decisions

### Decision 1: Annotate the archived change rather than correct it

Add a short superseded pointer to the archived artifacts naming the inaccurate
claims, and leave the body unedited.

- **Rationale**: The archive is a record of what was decided at the time, and
  the divergences are themselves informative — they show where implementation
  pressure overrode the plan. Rewriting it would erase that and create a second
  description of the system that can drift again, which is the failure mode
  this change exists to address. This matches the project's established archive
  practice of reducing a superseded document to a pointer rather than
  maintaining parallel descriptions.
- **Alternatives considered**:
  - *Rewrite the archived design to match the code*: destroys the historical
    record and re-creates the drift risk.
  - *Delete the archived change*: loses the rationale for decisions still
    embedded in the code.
  - *Leave it untouched*: a reader has no signal that it is wrong, which is the
    status quo being fixed.

### Decision 2: Justify each deletion with a positive check, not absence of use

Each removal is backed by a specific verification:

| Item | Evidence that it is dead |
| --- | --- |
| `discover_container_port()` | No reference anywhere in `tests/` or `src/`; the port is chosen by `find_free_port()` before the container starts, so nothing reads the engine's mapping back |
| `MEMORY` computation and `sed` in `entrypoint.sh` | `slurm.conf` contains no `<<MEMORY>>` placeholder, so the substitution matches nothing |
| `cgroup.conf` | `slurm.conf` sets `ProctrackType=proctrack/linuxproc` and `TaskPlugin=task/none`; Slurm reads `cgroup.conf` only when a cgroup-based proctrack or task plugin is selected |
| duplicated `chown`/`chmod` | The same ownership and mode are applied at Dockerfile build time; the entrypoint repetition changes nothing on a fresh container |
| `set -x`, `LogLevel DEBUG` | Diagnostic verbosity, not required by any assertion; the fixture's own error paths already capture container logs on failure |

- **Rationale**: "Nothing calls it" is weak evidence in a codebase with dynamic
  dispatch and shell indirection. Each row above states what *would* have to be
  true for the item to matter, and why it is not.
- **Alternatives considered**: *Leave the debugging aids in place* — they cost
  nothing at runtime, but `set -x` and `LogLevel DEBUG` inflate the log dump
  that the fixture emits on failure, which makes the failure harder to read,
  not easier.

### Decision 3: Defer anything that changes behaviour

The committed private key, the port-allocation strategy, the over-provisioned
remote virtual environment and the conflated readiness loop are all left alone.

- **Rationale**: Each requires a replacement mechanism (run-time public-key
  injection; reading the engine-assigned port back; a different install step;
  staged readiness checks), so none can be expressed as a deletion. Mixing them
  in would make this change require the container fixture to be exercised
  before it could be trusted, which is precisely the expensive step this change
  is designed to avoid needing.
- **Alternatives considered**: *Fix the port strategy here* — tempting, because
  the live spec already describes engine-assigned allocation and the code does
  not implement it. Rejected because verifying it needs a working container
  engine, which puts this change on the slow path.

## Risks / Trade-offs

- **[Risk] `cgroup.conf` is read by something not visible in `slurm.conf`** —
  for example a default compiled into the distribution's Slurm build.
  → *Mitigation*: the file's contents disable every constraint it configures
  (`ConstrainCores`, `ConstrainRAMSpace`, `ConstrainSwapSpace` all `no`), so
  even if it were read, removing it changes no enforced limit.

- **[Risk] The Dockerfile-side deletions are wasted if the container is later
  replaced wholesale.** → *Mitigation*: accepted deliberately. The cost is
  small and bounded, and the benefit is that the later rework arrives as a
  clean replacement rather than a diff entangled with cleanup.

- **[Trade-off] The change cannot be verified locally in a sandboxed
  development container.** A nested rootless container engine can only map a
  single UID, which forces `setgroups` to be denied for that namespace; OpenSSH
  privilege separation calls `setgroups` before authentication, so no SSH login
  can complete. Verification of the container path therefore depends on CI or a
  developer's own machine. This change is confined to deletions and prose
  specifically so that the risk of needing that verification is low.
