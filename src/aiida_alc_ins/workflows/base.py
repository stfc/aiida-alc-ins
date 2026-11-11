"""Abstract base WorkChains, one per reusable feature.

Two independent features are split into two abstract bases so that a workflow
inherits only what it needs:

* :class:`JobDispatchWorkChain` -- the ``code``/``options`` dispatch plumbing
  (inputs, ``get_job_metadata()`` and the ``400 ERROR_SUB_PROCESS_FAILED`` exit
  code) shared by every workflow that runs PythonJobs.
* :class:`FromForceConstantsWorkChain` -- obtaining force constants by running
  :class:`~aiida_alc_ins.workflows.force_constants.ForceConstantsWorkChain`
  as a sub-workflow, exposing its inputs under a ``force_constants`` namespace
  (so its "exactly one" validator lives in the namespace and cannot collide
  with a parent's own validator) and reporting its failure with ``402
  ERROR_SUB_PROCESS_FAILED_FORCE_CONSTANTS``.

Each base subclasses ``WorkChain`` directly (rather than being a plain mixin) so
its spec can be built and tested on its own, and neither references the other's
ports, methods or exit codes. Neither has an outline: consumers add their own,
starting ``cls.run_force_constants, cls.inspect_force_constants, ...`` where
they use the force-constants source. Plumpy's method resolution order builds one
spec through every base when a consumer subclasses several, provided each base's
``define`` calls ``super().define(spec)``.
"""

from __future__ import annotations

from typing import Any

from aiida.engine import ExitCode, ToContext, WorkChain
from aiida.orm import AbstractCode, Dict, to_aiida_type

from aiida_alc_ins.workflows.force_constants import ForceConstantsWorkChain


class JobDispatchWorkChain(WorkChain):
    """Abstract base providing ``code``/``options`` dispatch for PythonJobs.

    Exit Codes:
        * 400 (ERROR_SUB_PROCESS_FAILED): A PythonJob step did not finish
          successfully.
    """

    @classmethod
    def define(cls, spec) -> None:
        super().define(spec)
        spec.input(
            "code",
            valid_type=AbstractCode,
            help="Python code used to run the PythonJob steps.",
        )
        spec.input(
            "options",
            valid_type=Dict,
            required=False,
            serializer=to_aiida_type,
            help=(
                "Optional scheduler and execution options passed to child PythonJobs."
            ),
        )
        spec.exit_code(
            400,
            "ERROR_SUB_PROCESS_FAILED",
            message="A PythonJob step did not finish successfully.",
        )

    def get_job_metadata(self) -> dict[str, Any]:
        """Return metadata dictionary for child PythonJobs."""
        if "options" in self.inputs:
            return {"options": self.inputs.options.get_dict()}
        return {}


class FromForceConstantsWorkChain(WorkChain):
    """Abstract base obtaining force constants from a sub-workflow.

    Exposes the inputs of
    :class:`~aiida_alc_ins.workflows.force_constants.ForceConstantsWorkChain`
    under a required ``force_constants`` namespace and runs that workchain as a
    child to resolve ``self.ctx.force_constants``, always delegating to the
    child (even for a prepared node, which is passed through) so every run has
    exactly one ``ForceConstantsWorkChain`` in the provenance graph. Consumers
    start their outline with ``cls.run_force_constants, cls.inspect_force_constants``.

    Exit Codes:
        * 402 (ERROR_SUB_PROCESS_FAILED_FORCE_CONSTANTS): The
          ``ForceConstantsWorkChain`` sub-workflow did not finish successfully.
    """

    @classmethod
    def define(cls, spec) -> None:
        super().define(spec)
        spec.expose_inputs(
            ForceConstantsWorkChain,
            namespace="force_constants",
        )
        spec.exit_code(
            402,
            "ERROR_SUB_PROCESS_FAILED_FORCE_CONSTANTS",
            message=(
                "The ForceConstantsWorkChain sub-workflow did not finish successfully."
            ),
        )

    def run_force_constants(self):
        """Submit the ``ForceConstantsWorkChain`` child with exposed inputs."""
        inputs = self.exposed_inputs(
            ForceConstantsWorkChain, namespace="force_constants"
        )
        return ToContext(
            force_constants_workchain=self.submit(ForceConstantsWorkChain, **inputs)
        )

    def inspect_force_constants(self) -> ExitCode | None:
        """Store the child's output, or fail with 402 if it did not finish ok."""
        workchain = self.ctx.force_constants_workchain
        if not workchain.is_finished_ok:
            self.report(
                f"ForceConstantsWorkChain failed with exit code {workchain.exit_status}"
            )
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED_FORCE_CONSTANTS
        self.ctx.force_constants = workchain.outputs.force_constants
        return None
