# Design

## Context

See `proposal.md` for the motivation behind this change.

In AiiDA's execution architecture:
- `CalcJob` (such as `PythonJob`) represents a calculation executed by a batch scheduler on a `Computer`. It defines an input port namespace `metadata.options` containing execution and scheduler directives (`resources`, `max_wallclock_seconds`, `queue_name`, etc.).
- `WorkChain` represents an orchestrator executed by the local daemon process. It does not execute under a batch scheduler and its `metadata` namespace contains only process-level metadata (`label`, `description`, `store_provenance`), not `options`.
- In `aiida-hyperqueue`, `HyperQueueJobResource` requires task-based resources (`num_cpus` and optional `memory_mb`). If `num_cpus` is omitted, it falls back to `num_machines * num_mpiprocs_per_machine` and emits `AiiDAHypereQueueDeprecationWarning`.
- In `aiida-pythonjob`, `PythonJob` defines default resources `{"num_machines": 1, "num_mpiprocs_per_machine": 1}` for compatibility with traditional HPC schedulers (Slurm, PBS).
- Currently, `aiida_pythonjob_ins` workflows (`ForceConstantsWorkChain`, `DosWorkChain`, `DispersionWorkChain`, `ToscaFromModesWorkChain`, `ToscaFromForceConstantsWorkChain`) have no port to accept execution options, leaving child `PythonJob`s with default machine resources and triggering the deprecation warning on HyperQueue.

## Goals / Non-Goals

**Goals:**
- Provide an idiomatic AiiDA workflow interface for users to supply scheduler and runtime options (`resources`, wallclock limits, queue names).
- Automatically forward configured options from the parent WorkChain down to every child `PythonJob` calculation.
- Support options in `pythonjobs.py` input builders (`prepare_*_inputs`) for standalone job preparation.
- Update remote containerized integration tests to declare HyperQueue-native resources (`num_cpus=1`).
- Remove the warning suppression rule for `AiiDAHypereQueueDeprecationWarning` from `pyproject.toml`.

**Non-Goals:**
- Modifying upstream `aiida-pythonjob` default resources or `aiida-hyperqueue` scheduler validation logic.
- Introducing multi-namespace per-step options (e.g. `read_options` vs `dos_options`); child steps share a common compute environment.

## Decisions

### 1. Dedicated `options` input port on WorkChains (`valid_type=orm.Dict`, `serializer=orm.to_aiida_type`)

*Decision*: Add `spec.input("options", valid_type=orm.Dict, required=False, serializer=orm.to_aiida_type)` to `ForceConstantsWorkChain` and `ToscaFromModesWorkChain`.

*Rationale*:
- In AiiDA workflows that orchestrate `CalcJob`s, defining an `options` port of type `orm.Dict` is the standard ecosystem pattern (see AiiDA Core documentation on [Writing Workflows](https://aiida.readthedocs.io/projects/aiida-core/en/latest/howto/write_workflows.html) and Quantum ESPRESSO's `PwBaseWorkChain` / `PwBandsWorkChain`).
- Using `serializer=orm.to_aiida_type` allows callers to provide either a native Python `dict` (e.g. `options={"resources": {"num_cpus": 1}}`) or an existing `orm.Dict` node.
- Provenance tracking: Storing `options` as an `orm.Dict` node records the requested execution resources in the workflow's provenance graph, whereas storing them in `metadata` would discard them from provenance.

*Alternatives Considered*:
- *Exposing `PythonJob` ports via `spec.expose_inputs(PythonJob, namespace="...")`*: Rejected because `PythonJob` contains low-level plumbing ports (`function_data`, `serializers`, `upload_files`, `parent_folder`) managed internally by `prepare_*_inputs`. Exposing the raw process spec would leak internal implementation details to workflow callers.
- *Adding `spec.input("metadata.options", ...)`*: Rejected because `metadata` on a WorkChain is reserved by `aiida-core` for non-database process attributes.

### 2. Workflow-wide options sharing across child steps

*Decision*: A single `options` input applies to all child `PythonJob` calculations dispatched by the workflow.

*Rationale*:
- In `aiida_pythonjob_ins`, all compute steps (`read_force_constants`, `compute_dos`, `interpolate`, `compute_intensities`) run lightweight Python/Euphonic functions.
- All steps share the same `code` input targeting the same `Computer`.
- Real execution times on typical crystals range from 1 to 20 seconds. Splitting options into per-step ports (`read_options`, `dos_options`) would add verbosity with virtually no operational benefit.

*Alternatives Considered*:
- *Per-step option ports*: Rejected as unnecessary complexity for currently envisaged workflows. If step-specific overrides are ever needed in the future, optional per-step override ports (e.g. `dos_options`) can be added without breaking the common `options` port.

### 3. Base helper `get_job_metadata()` in `ForceConstantsWorkChain`

*Decision*: Provide a helper method `get_job_metadata()` on `ForceConstantsWorkChain` and `ToscaFromModesWorkChain`:
```python
def get_job_metadata(self) -> dict[str, Any]:
    """Return metadata dictionary for child PythonJobs."""
    if "options" in self.inputs:
        return {"options": self.inputs.options.get_dict()}
    return {}
```

*Rationale*:
- Centralizes formatting of `metadata={"options": ...}` for child `prepare_*_inputs` calls.
- Subclasses (`DosWorkChain`, `DispersionWorkChain`, `ToscaFromForceConstantsWorkChain`) inherit the helper directly, passing `metadata=self.get_job_metadata()` to their input builders.
- When `options` is not supplied, it returns `{}` so child jobs continue using standard defaults without regression.
- In `ToscaFromForceConstantsWorkChain.compute_spectrum()`, if top-level `options` is provided and the delegated `spectrum` namespace does not define its own, the top-level `options` is forwarded to `ToscaFromModesWorkChain`.

### 4. Direct `metadata={"options": ...}` forwarding in `pythonjobs.py` input builders

*Decision*: Rely on standard AiiDA `metadata={"options": ...}` forwarding via `**kwargs` in all `prepare_*_inputs` functions, accompanied by explicit docstring examples.

*Rationale*:
- In AiiDA, `options` for a `CalcJob` naturally belongs inside `metadata["options"]`. Introducing a parallel `options` parameter to `prepare_*_inputs` introduced ambiguity about which dictionary callers should populate and required custom merging logic.
- Upstream `prepare_pythonjob_inputs` already accepts `metadata` and merges it into its internal metadata specifications. Forwarding `**kwargs` directly allows callers to pass standard `metadata={"options": {"resources": ...}}` without any custom merging abstraction in this package.
- Clear parameter documentation and examples in each function's docstring ensure discoverability.

### 5. Test suite update and warning filter removal

*Decision*: Update `tests/test_remote_ssh.py` to supply `metadata={"options": {"resources": {"num_cpus": 1}}}` in `test_pythonjob_remote_ssh` and `options={"resources": {"num_cpus": 1}}` in `test_dos_workchain_remote_ssh`, and delete the warning suppression line in `pyproject.toml`.

*Rationale*:
- The warning suppression line was a temporary workaround. Suppressing `AiiDAHypereQueueDeprecationWarning` hid the fact that workflows were unable to configure scheduler options.
- Removing the filter ensures that any future regression to deprecated scheduler options will fail CI immediately.

## Risks / Trade-offs

- **[Risk: Caller runs on HyperQueue without specifying `options`]** → Mitigation: HyperQueue scheduler plugin will emit its standard deprecation warning, alerting the user to configure scheduler resources. Localhost executions remain unaffected.
