# Tasks

## 1. Input Builders (`pythonjobs.py`)

- [x] 1.1 Document `metadata={"options": ...}` forwarding and provide explicit docstring examples across all `prepare_*_inputs` functions in `src/aiida_pythonjob_ins/pythonjobs.py`.
- [x] 1.2 Add unit tests in `tests/test_pythonjobs.py` confirming that `metadata` (including `metadata["options"]`) and non-metadata execution kwargs are forwarded cleanly. Verify with `uv run pytest tests/test_pythonjobs.py`.

## 2. Workflows (`workflows/`)

- [x] 2.1 Add `options` input port (`valid_type=orm.Dict`, `serializer=orm.to_aiida_type`, `required=False`) and `get_job_metadata()` helper to `ForceConstantsWorkChain` in `src/aiida_pythonjob_ins/workflows/base.py`, and pass `metadata=self.get_job_metadata()` in `read_force_constants()`.
- [x] 2.2 Update `DosWorkChain` in `src/aiida_pythonjob_ins/workflows/dos.py` to pass `metadata=self.get_job_metadata()` in `compute_dos()`.
- [x] 2.3 Update `DispersionWorkChain` in `src/aiida_pythonjob_ins/workflows/dispersion.py` to pass `metadata=self.get_job_metadata()` in `interpolate()`.
- [x] 2.4 Add `options` input port and `get_job_metadata()` helper to `ToscaFromModesWorkChain` in `src/aiida_pythonjob_ins/workflows/tosca.py`, passing `metadata=self.get_job_metadata()` in `compute_intensities()`.
- [x] 2.5 Update `ToscaFromForceConstantsWorkChain` in `src/aiida_pythonjob_ins/workflows/tosca.py` to pass `metadata=self.get_job_metadata()` in `interpolate_modes()` and forward `options` to child `ToscaFromModesWorkChain` in `compute_spectrum()`.
- [x] 2.6 Add unit tests in `tests/test_workflows.py` verifying that supplying `options` to workflows links the `options` input node in provenance and propagates the options to called `PythonJob` descendants. Verify with `uv run pytest tests/test_workflows.py`.

## 3. Remote Container Tests and Warning Cleanup

- [x] 3.1 Update `test_pythonjob_remote_ssh` in `tests/test_remote_ssh.py` to supply `metadata={"options": {"resources": {"num_cpus": 1}}}`.
- [x] 3.2 Update `test_dos_workchain_remote_ssh` in `tests/test_remote_ssh.py` to supply `options={"resources": {"num_cpus": 1}}`.
- [x] 3.3 Remove `"ignore:.*setting hyperqueue resources are deprecated.*:aiida_hyperqueue.scheduler.AiiDAHypereQueueDeprecationWarning"` from `filterwarnings` in `pyproject.toml`.
- [x] 3.4 Run `uv run pytest tests/test_remote_ssh.py -W error::aiida_hyperqueue.scheduler.AiiDAHypereQueueDeprecationWarning` to verify that container integration tests pass cleanly without triggering scheduler deprecation warnings.
- [x] 3.5 Run full validation (`uv run pytest` and `uv run ruff check`) to verify overall test suite and code quality health.
