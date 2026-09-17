# Proposal

## Why

When testing containerized workflows against HyperQueue, `aiida-hyperqueue` emits a deprecation warning (`AiiDAHypereQueueDeprecationWarning`) because `PythonJob` defaults to machine-based scheduler resources (`{"num_machines": 1, "num_mpiprocs_per_machine": 1}`) rather than HyperQueue's required task-based resources (`{"num_cpus": int}`). A previous test update silenced this via a warning filter in `pyproject.toml`.

The underlying issue is that `aiida_pythonjob_ins` WorkChains currently provide no port or mechanism for callers to specify scheduler options, making it impossible to pass `num_cpus` (or queue names, wallclock limits, or custom scheduler directives) to child `PythonJob`s. Workflows should allow callers to supply execution and scheduler options idiomatically, forward those options to underlying calculation steps, exercise this in containerized integration tests, and remove the warning suppression filter.

## What Changes

- Add an optional `options` input port (`valid_type=orm.Dict`, `serializer=orm.to_aiida_type`) to `ForceConstantsWorkChain` (inherited by `DosWorkChain`, `DispersionWorkChain`, and `ToscaFromForceConstantsWorkChain`) and `ToscaFromModesWorkChain`.
- Add a helper method on the base WorkChain to format child job metadata, passing configured options down as `metadata={"options": ...}` to every child `PythonJob` invocation.
- Document the standard `metadata={"options": {"resources": ...}}` pattern with clear docstring examples across `pythonjobs.py` input builders (`prepare_*_inputs`).
- Update containerized integration tests (`test_remote_ssh.py`) to pass HyperQueue resources (`num_cpus=1`) into `PythonJob` (`metadata={"options": ...}`) and `DosWorkChain` (`options={...}`) runs on the remote container.
- Remove the warning filter ignoring `AiiDAHypereQueueDeprecationWarning` from `pyproject.toml`.

## Non-goals

- Redesigning `aiida-pythonjob`'s upstream defaults for `metadata.options.resources`.
- Adding per-step option namespaces (such as separate `read_options` and `dos_options`); all child steps in currently-envisaged workflows target the same code on the same compute resource and share a common execution options specification.
- Changing scientific physics inputs (e.g. `q_spacing`, `energy_spacing`, `temperature`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `phonon-workflows`: Workflows accept an optional `options` input port and forward execution/scheduler options to child `PythonJob` steps.
- `testing-and-ci`: Containerized integration tests supply explicit scheduler resources to remote jobs, and the test suite executes without suppressing `AiiDAHypereQueueDeprecationWarning`.

## Impact

- **APIs**: `ForceConstantsWorkChain`, `DosWorkChain`, `DispersionWorkChain`, `ToscaFromModesWorkChain`, and `ToscaFromForceConstantsWorkChain` gain an optional `options` input port. Input builders document `metadata={"options": ...}` forwarding. Existing calls omitting `options` retain their current default behavior.
- **Dependencies**: No new dependencies.
- **Tests**: Containerized integration tests in `tests/test_remote_ssh.py` explicitly declare HyperQueue resources; `pyproject.toml` warning suppression is eliminated.
