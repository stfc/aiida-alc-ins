"""Shared base WorkChain that obtains force constants for a phonon calculation.

The concrete workflows (dispersion, DOS) all need a ``ForceConstantsData`` to work
from. This base lets that come from *either*:

* a CASTEP ``castep_file`` (``SinglefileData``) -- read in-workflow by a PythonJob
  (demonstrating file staging), or
* a pre-built ``force_constants`` (``ForceConstantsData``) node -- e.g. produced
  from Phonopy input (see
  :func:`aiida_pythonjob_ins.pythonjobs.prepare_read_phonopy_inputs`) or any other
  source.

Subclasses add their own inputs/outputs and an outline that begins with::

    if_(cls.should_read_castep)(cls.read_force_constants),
    cls.assign_force_constants,
    ...  # their compute steps, using ``self.ctx.force_constants``

Reading Phonopy inside the workflow is intentionally *not* built in here: Phonopy
needs several files, so it is cleaner to read it up front into a
``ForceConstantsData`` and pass that as ``force_constants``.
"""

from __future__ import annotations

from typing import Any

from aiida.engine import ToContext, WorkChain
from aiida.orm import AbstractCode, Dict, SinglefileData, to_aiida_type
from aiida_pythonjob import PythonJob

from aiida_pythonjob_ins.data import ForceConstantsData
from aiida_pythonjob_ins.pythonjobs import prepare_read_force_constants_inputs


class ForceConstantsWorkChain(WorkChain):
    """Resolve ``self.ctx.force_constants`` from a CASTEP file or a given node.

    Exit Codes:
        * 400 (ERROR_SUB_PROCESS_FAILED): A PythonJob step did not finish successfully.
    """

    @classmethod
    def define(cls, spec) -> None:
        super().define(spec)
        spec.input(
            "castep_file",
            valid_type=SinglefileData,
            required=False,
            help="CASTEP .castep_bin/.check file (read in-workflow via a PythonJob).",
        )
        spec.input(
            "force_constants",
            valid_type=ForceConstantsData,
            required=False,
            help="Pre-built force constants (e.g. from Phonopy); skips the read step.",
        )
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
            help="Optional scheduler and execution options passed to child PythonJobs.",
        )
        spec.inputs.validator = cls._validate_source
        spec.exit_code(
            400,
            "ERROR_SUB_PROCESS_FAILED",
            message="A PythonJob step did not finish successfully.",
        )

    @staticmethod
    def _validate_source(inputs, _port) -> str | None:
        """Require exactly one of ``castep_file`` / ``force_constants``."""
        has_file = "castep_file" in inputs
        has_fc = "force_constants" in inputs
        if has_file == has_fc:
            return "Provide exactly one of `castep_file` or `force_constants`."
        return None

    def get_job_metadata(self) -> dict[str, Any]:
        """Return metadata dictionary for child PythonJobs."""
        if "options" in self.inputs:
            return {"options": self.inputs.options.get_dict()}
        return {}

    def should_read_castep(self) -> bool:
        """Outline predicate: read a CASTEP file only if no node was supplied."""
        return "force_constants" not in self.inputs

    def read_force_constants(self):
        """Read force constants from the CASTEP file via a PythonJob."""
        inputs = prepare_read_force_constants_inputs(
            self.inputs.castep_file,
            code=self.inputs.code,
            metadata=self.get_job_metadata(),
        )
        return ToContext(read=self.submit(PythonJob, **inputs))

    def assign_force_constants(self):
        """Set ``self.ctx.force_constants`` from the input node or the read step."""
        if "force_constants" in self.inputs:
            self.ctx.force_constants = self.inputs.force_constants
        elif self.ctx.read.is_finished_ok:
            self.ctx.force_constants = self.ctx.read.outputs.result
        else:
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED
        return None
