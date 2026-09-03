# Tidy the Slurm test infrastructure

## Why

The archived `2026-08-25-add-slurm-integration-tests` change records a design
that was abandoned during implementation: it recommends a base image that is
unusable, states that SSH keys are generated in memory when a private key is in
fact committed to the repository, and claims a port-allocation strategy the code
does not use. Alongside it, the implementation left behind code that is never
called and debugging aids that were never switched off.

This project is explicitly an exemplar, so a reader who follows either the
archived design or the shipped scaffolding is misled. Neither problem is a
behaviour change: this change corrects documentation and removes provably unused
code, and nothing about what the test suite verifies is altered.

## What Changes

### Correct the record

- Add a "superseded" pointer to the archived change's `proposal.md`,
  `design.md` and `tasks.md`, naming the specific claims that do not describe
  the shipped system. The artifacts are otherwise left unedited as a record of
  the original reasoning.
- Correct the `slurm_container` fixture docstring in `tests/conftest.py`, which
  states that the fixture runs `ghcr.io/aiidateam/slurm-image`. It runs a
  locally built image, and that registry path is the option the archived design
  explicitly rejected.
- Record the container-registry findings that motivated the correction, so the
  question is not re-investigated: anonymous pulls from GHCR succeed for other
  `aiidateam` packages, and the image the archived design recommends is a
  six-year-old Ubuntu 16.04 build carrying Python 3.5.

### Remove vestigial code

- `tests/slurm_support.py`: delete `discover_container_port()`, which no caller
  references.
- `tests/container/entrypoint.sh`: delete the `MEMORY` computation and its
  `sed` substitution, for which no placeholder exists in `slurm.conf`; remove
  `set -x`; remove the `chown`/`chmod` lines already performed at image build
  time.
- `tests/container/cgroup.conf`: delete the file and the `COPY` that installs
  it. `slurm.conf` selects `proctrack/linuxproc` and `task/none`, so no Slurm
  component reads it.
- `tests/container/Dockerfile`: remove `LogLevel DEBUG` from the generated
  `sshd_config`, and the duplicated ownership fix-ups.

## Capabilities

### New Capabilities

*(None)*

### Modified Capabilities

*(None. No requirement in `testing-and-ci` changes: the suite verifies exactly
what it verified before. `skip_specs: true` is set in `.openspec.yaml`.)*

## Non-goals

- **Replacing, rebasing or restructuring the container image.** Whether the
  integration test should drop Slurm, adopt an upstream base image, or be
  rebuilt around SSH alone is still being explored and is deliberately out of
  scope here.
- **Removing the committed private key** `tests/container/id_rsa`. It cannot go
  until the public key is injected at run time instead of baked into the image,
  which is a behaviour change belonging to the container rework.
- **Changing how the SSH port is allocated.** The code picks a free port in
  Python rather than letting the engine assign one, which is what the live spec
  describes; correcting that is a behaviour change and belongs with the rework.
- **Adding, removing or re-scoping any test.**

## Impact

- `openspec/changes/archive/2026-08-25-add-slurm-integration-tests/`:
  `proposal.md`, `design.md`, `tasks.md` gain a superseded pointer.
- `tests/conftest.py`: docstring correction only.
- `tests/slurm_support.py`: one unused function removed.
- `tests/container/`: `cgroup.conf` deleted; `Dockerfile` and `entrypoint.sh`
  lose debugging residue and duplicated setup.

No source module, dependency, entry point or public API is touched. If a later
change replaces `tests/container/` wholesale, the deletions made here to those
files become moot; they are made now so that the tree is honest in the
meantime and the later diff is legible rather than tangled with cleanup.
