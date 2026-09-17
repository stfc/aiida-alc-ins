"""A WorkChain computing a phonon density of states.

After :class:`ForceConstantsWorkChain` resolves the force constants (read from a
CASTEP file via a PythonJob, or taken from a supplied node), a single PythonJob
samples a Monkhorst-Pack grid and computes the DOS; the euphonic ``Spectrum1D`` is
serialized to a native ``XyData`` for easy plotting.
"""

from __future__ import annotations

from aiida.engine import ToContext, if_
from aiida.orm import Float, XyData
from aiida_pythonjob import PythonJob

from aiida_pythonjob_ins.pythonjobs import prepare_dos_inputs
from aiida_pythonjob_ins.workflows.base import ForceConstantsWorkChain


class DosWorkChain(ForceConstantsWorkChain):
    """Compute a phonon DOS from a CASTEP file or a ForceConstantsData node.

    Exit Codes:
        * 400 (ERROR_SUB_PROCESS_FAILED): A PythonJob step did not finish successfully.
    """

    @classmethod
    def define(cls, spec) -> None:
        super().define(spec)  # castep_file / force_constants / code + validator
        spec.input(
            "q_spacing",
            valid_type=Float,
            default=lambda: Float(0.1),
            help="Target Monkhorst-Pack grid spacing, in 1/Angstrom.",
        )
        spec.input(
            "energy_spacing",
            valid_type=Float,
            default=lambda: Float(1.0),
            help="DOS energy bin width, in meV.",
        )
        spec.outline(
            if_(cls.should_read_castep)(cls.read_force_constants),
            cls.assign_force_constants,
            cls.compute_dos,
            cls.finalize,
        )
        spec.output(
            "dos",
            valid_type=XyData,
            help="Phonon density of states (energy vs DOS).",
        )

    def compute_dos(self):
        """Sample a grid and compute the DOS."""
        inputs = prepare_dos_inputs(
            self.ctx.force_constants,
            q_spacing=self.inputs.q_spacing.value,
            energy_spacing=self.inputs.energy_spacing.value,
            code=self.inputs.code,
            metadata=self.get_job_metadata(),
        )
        return ToContext(dos=self.submit(PythonJob, **inputs))

    def finalize(self):
        """Expose the DOS XyData."""
        if not self.ctx.dos.is_finished_ok:
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED
        self.out("dos", self.ctx.dos.outputs.result)
        return None
