# Document running PythonJobs on SSH and scheduled computers

> **Status: proposal only.** Recorded so the investigation behind it is not
> lost. `specs/`, `design.md` and `tasks.md` are not yet written, so this change
> does not validate. Depends on `replace-slurm-container-with-ssh` landing
> first, because the how-to includes configuration from that fixture.

## Why

Everything the project knows about running these jobs somewhere other than
`localhost` currently exists only as test code, and the one attempt to describe
it in prose diverged from the implementation in five separate places. The
lesson is not that the prose was careless but that a hand-written parallel
description of a live configuration will drift.

There is also a genuinely useful fact to publish that is not obvious from the
upstream documentation: **a remote execution environment for `aiida-pythonjob`
needs no AiiDA installation at all.** The generated job script imports only
`sys`, `json`, `traceback`, `cloudpickle`, plus `node_graph` and optionally
`mpi4py`. Anyone provisioning a compute-node environment for this plugin is
otherwise likely to install the whole AiiDA stack unnecessarily.

Finally, scheduler behaviour is outside this project's control: anyone on real
HPC must configure a computer against their own scheduler, queues and resource
policies. A tutorial they can follow and adapt is worth more than a green tick
in this repository's CI that does not transfer.

One incidental finding worth acting on: aiida-core's testing fixtures for SSH
computers and key generation are not documented in its current release. The API
reference page for them exists up to version 2.7.1 and returns not-found for
2.8.0 onwards, including the version this project depends on. A page here that
describes them accurately may be among the few available; it is also worth
raising upstream.

## What Changes

- Add a how-to page covering configuration of an AiiDA `Computer` for
  `core.ssh` transport and an `InstalledCode` pointing at a remote interpreter,
  with the connection and code configuration **included from the integration
  test fixture** rather than transcribed. What CI proves and what the page shows
  then cannot diverge.
- Document the remote environment contract explicitly, including that AiiDA is
  not required there and what actually is.
- Add a walkthrough for a scheduled computer using the containerized Slurm
  setup, written to be run by a human rather than by CI. This absorbs what was
  previously scoped as an occasional Slurm test tier.
- State the environment prerequisites for following each page.

## Capabilities

### Modified Capabilities

- `documentation`: add requirements covering guidance for remote and scheduled
  execution, and the constraint that configuration shown in the documentation is
  taken from the tested fixture rather than duplicated.

## Non-goals

- **A sphinx-gallery example.** The gallery executes at build time, so an
  example requiring a container engine would break the documentation build
  anywhere one is absent. This is prose with included snippets, not an executed
  example.
- **A CI job for the Slurm walkthrough.** It is documentation. A scheduled run
  could be added later if the regression signal is wanted, but that is not the
  reason for it to exist.
- **Documenting AiiDA's own scheduler plugins.** Point at upstream
  documentation rather than restating it.

## Impact

- `docs/source/`: one how-to page and one tutorial page, plus navigation.
- Snippet inclusion couples the documentation build to the test fixture's file
  layout; region markers should be chosen so that ordinary edits do not silently
  change what the documentation shows.
- No source module, dependency, entry point or public API is touched.

## Open questions

- Whether the Slurm walkthrough keeps a container at all, or documents
  connecting to a real cluster with a container as an optional local rehearsal.
- Whether the how-to should also cover `core.ssh_async`, which aiida-core ships
  alongside `core.ssh`.
