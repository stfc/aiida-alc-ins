"""A WorkChain composing Euphonic steps into a dispersion workflow.

Steps (after force constants are resolved by :class:`ForceConstantsWorkChain` --
read from a CASTEP file via a PythonJob, or taken from a supplied node):

1. extract the crystal structure            -> StructureData       (calcfunction)
2. generate a seekpath q-point path          -> KpointsData         (calcfunction)
3. interpolate phonon modes on that path    -> QpointPhononModesData (PythonJob)
4. compose a band structure                 -> BandsData           (calcfunction)

The ``calcfunction`` steps run in-process (they need a loaded AiiDA profile to
build nodes and are cheap), while the compute-heavy interpolate step runs as a
``PythonJob`` that could target a remote machine. Building the band path
parent-side lets it return a native ``KpointsData`` directly -- no custom carrier
type needed. ``BandsData`` plugs into AiiDA's plotting, e.g.
``results['band_structure'].show_mpl()``.

WorkChain reference:
https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/workflows/write.html
"""

from __future__ import annotations

from aiida.engine import ToContext, calcfunction, if_
from aiida.orm import BandsData, Float, KpointsData, StructureData
from aiida_pythonjob import PythonJob

from aiida_pythonjob_ins.conversions import (
    qpoints_to_kpoints_data,
    structure_to_spglib_cell,
)
from aiida_pythonjob_ins.data import QpointPhononModesData
from aiida_pythonjob_ins.data.mixins import SupportsToStructure
from aiida_pythonjob_ins.operations import band_path_qpoints
from aiida_pythonjob_ins.pythonjobs import prepare_interpolation_inputs
from aiida_pythonjob_ins.workflows.base import ForceConstantsWorkChain


@calcfunction
def extract_structure(data: SupportsToStructure) -> StructureData:
    """Extract a ``StructureData`` from any node implementing ``to_structure()``.

    Generic on purpose: it works for ``ForceConstantsData``,
    ``QpointPhononModesData``, or any future node exposing ``to_structure()`` (the
    ``SupportsToStructure`` protocol). It is just a calcfunction wrapper so the
    method call becomes a provenance link between the input node and the
    ``StructureData`` on the workflow graph. AiiDA infers ``valid_type=(Data,)``
    from the protocol annotation; the ``to_structure()`` call does the rest.
    """
    return data.to_structure()


@calcfunction
def generate_band_path(structure: StructureData, q_spacing: Float) -> KpointsData:
    """Build a seekpath high-symmetry q-point path as a native ``KpointsData``.

    Depends only on the crystal *structure* (seekpath needs nothing else). A
    parent-side ``calcfunction`` (not a PythonJob): path-building is cheap and
    needs a loaded profile to construct the ``KpointsData`` node, which a remote
    PythonJob subprocess could not do.
    """
    cell = structure_to_spglib_cell(structure)
    path = band_path_qpoints(cell, q_spacing.value)
    return qpoints_to_kpoints_data(path.qpoints, path.cell, labels=path.labels)


@calcfunction
def assemble_bands(modes: QpointPhononModesData, qpoints: KpointsData) -> BandsData:
    """Compose a BandsData from phonon modes + the labelled q-point path.

    A ``calcfunction`` (so the BandsData is provenance-linked) that just delegates
    to the Data node's own converter; ``qpoints`` supplies the high-symmetry labels
    that Euphonic modes do not carry.
    """
    return modes.to_bands(qpoints)


class DispersionWorkChain(ForceConstantsWorkChain):
    """Compute phonon dispersion from a CASTEP file or a ForceConstantsData node.

    Exit Codes:
        * 400 (ERROR_SUB_PROCESS_FAILED): A PythonJob step did not finish successfully.
    """

    @classmethod
    def define(cls, spec) -> None:
        super().define(spec)  # castep_file / force_constants / code + validator
        spec.input(
            "q_spacing",
            valid_type=Float,
            default=lambda: Float(0.025),
            help="Target q-point spacing along the band path, in 1/Angstrom.",
        )
        spec.outline(
            if_(cls.should_read_castep)(cls.read_force_constants),
            cls.assign_force_constants,
            cls.generate_path,
            cls.interpolate,
            cls.finalize,
        )
        spec.output(
            "phonon_modes",
            valid_type=QpointPhononModesData,
            help="Frequencies + eigenvectors along the band path.",
        )
        spec.output(
            "structure",
            valid_type=StructureData,
            help="Crystal structure extracted from the force constants.",
        )
        spec.output(
            "band_path",
            valid_type=KpointsData,
            help="The high-symmetry q-point path (positions + labels).",
        )
        spec.output(
            "band_structure",
            valid_type=BandsData,
            help="Phonon band structure (frequencies as bands) for plotting.",
        )

    def generate_path(self):
        """Extract the structure, then build the q-point path.

        Both are parent-side calcfunctions (cheap, and they build AiiDA nodes).
        seekpath needs only the structure, so we materialize a ``StructureData``
        first -- reusable and idiomatic -- then derive the path from it.
        """
        # calcfunctions run synchronously and return their output node directly.
        self.ctx.structure = extract_structure(self.ctx.force_constants)
        self.ctx.path = generate_band_path(self.ctx.structure, self.inputs.q_spacing)
        return

    def interpolate(self):
        """Interpolate phonon modes on the q-point path."""
        inputs = prepare_interpolation_inputs(
            self.ctx.force_constants,
            self.ctx.path,
            code=self.inputs.code,
            metadata=self.get_job_metadata(),
        )
        return ToContext(modes=self.submit(PythonJob, **inputs))

    def finalize(self):
        """Expose the modes, path and a composed BandsData."""
        if not self.ctx.modes.is_finished_ok:
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED

        qpoints = self.ctx.path
        modes = self.ctx.modes.outputs.result
        self.out("phonon_modes", modes)
        self.out("structure", self.ctx.structure)
        self.out("band_path", qpoints)
        self.out("band_structure", assemble_bands(modes, qpoints))
        return None
