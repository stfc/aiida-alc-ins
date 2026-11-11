"""WorkChains composing the TOSCA scattering-intensity operations.

Two chains, split by input rather than combined into one with an either/or port:
a required parameter for one input (`q_spacing`) would be meaningless for the
other, which a flat process spec cannot express honestly.

* :class:`ToscaFromModesWorkChain` -- the stable core. Takes prepared phonon
  modes and nothing else as a source; independently runnable.
* :class:`ToscaFromForceConstantsWorkChain` -- resolves force constants
  by running
  :class:`~aiida_alc_ins.workflows.force_constants.ForceConstantsWorkChain`
  as a sub-workflow (it genuinely is a force-constants-sourced chain) while
  **composing** :class:`ToscaFromModesWorkChain` through AiiDA's exposed-input/output
  machinery, mirroring `PwBandsWorkChain` exposing `PwBaseWorkChain`
  (https://github.com/aiidateam/aiida-quantumespresso/blob/main/src/aiida_quantumespresso/workflows/pw/bands.py).

`ToscaFromModesWorkChain` runs three provenance steps, split so that a change to
one input does not invalidate the others under caching:

1. ``compute_intensities`` -- a PythonJob computing the full, ungrouped line set
   (every atom x quantum-order x detector-angle component). Expensive; the step
   this design exists to make reusable.
2. ``group_spectra`` -- a cheap ``calcfunction`` grouping/summing that line set by
   caller-supplied metadata keys.
3. ``broaden_spectra`` -- a cheap ``calcfunction`` applying TOSCA's resolution
   broadening to the grouped result. Broadening after grouping is
   exact, not approximate: the resolution operator is linear, so
   ``broaden(sum(y)) == sum(broaden(y))``.
"""

from __future__ import annotations

from aiida.common import AttributeDict
from aiida.engine import ExitCode, ToContext, calcfunction
from aiida.orm import Float, List, Str, XyData
from aiida_pythonjob import PythonJob

from aiida_alc_ins.conversions import (
    spectrum_collection_to_xydata,
    xydata_to_spectrum_collection,
)
from aiida_alc_ins.data import QpointPhononModesData
from aiida_alc_ins.operations import broaden_tosca_spectrum
from aiida_alc_ins.pythonjobs import (
    prepare_grid_interpolation_inputs,
    prepare_tosca_spectrum_inputs,
)
from aiida_alc_ins.workflows.base import (
    FromForceConstantsWorkChain,
    JobDispatchWorkChain,
)


@calcfunction
def group_spectra(components: XyData, group_by: List) -> XyData:
    """Group/sum the full TOSCA line set by the requested metadata keys.

    Empty keys yield a single total line: Euphonic's ``group_by()`` with no keys
    already returns a one-line ``Spectrum1DCollection`` (unlike ``sum()``, which
    returns a bare ``Spectrum1D``), so routing both cases through ``group_by``
    keeps this function's return type -- and therefore the conversion back to
    ``XyData`` -- uniform.
    """
    collection = xydata_to_spectrum_collection(components)
    grouped = collection.group_by(*group_by.get_list())
    return spectrum_collection_to_xydata(grouped)


@calcfunction
def broaden_spectra(grouped: XyData, resolution_model: Str) -> XyData:
    """Apply TOSCA resolution broadening to an already-grouped line set."""
    collection = xydata_to_spectrum_collection(grouped)
    broadened = broaden_tosca_spectrum(collection, resolution_model.value)
    return spectrum_collection_to_xydata(broadened)


class ToscaFromModesWorkChain(JobDispatchWorkChain):
    """Compute a TOSCA spectrum from prepared phonon modes.

    Takes a ``QpointPhononModesData`` node and nothing else as a source: no
    file-reading step is offered, so this chain carries no q-point sampling
    parameter (that belongs to :class:`ToscaFromForceConstantsWorkChain`, which
    composes this one). The node-taking chain is the stable centre; any
    file-ingesting convenience composes around it rather than altering the core.

    Exit Codes:
        * 400 (ERROR_SUB_PROCESS_FAILED): The intensity PythonJob did not finish
          successfully.
    """

    @classmethod
    def define(cls, spec) -> None:
        super().define(spec)
        spec.input(
            "modes",
            valid_type=QpointPhononModesData,
            help="Precomputed phonon modes to simulate a TOSCA spectrum from.",
        )
        spec.input(
            "temperature",
            valid_type=Float,
            default=lambda: Float(10.0),
            help="Sample temperature in kelvin (governs Debye-Waller attenuation).",
        )
        spec.input(
            "energy_spacing",
            valid_type=Float,
            default=lambda: Float(10.0),
            help="Energy bin width, in `energy_unit`.",
        )
        spec.input(
            "energy_max",
            valid_type=Float,
            default=lambda: Float(4000.0),
            help=(
                "Instrument-range cutoff on the energy axis, in `energy_unit`. "
                "TOSCA results are conventionally examined up to 4000 cm-1, "
                "comfortably inside the ~8000 cm-1 the instrument can reach."
            ),
        )
        spec.input(
            "energy_unit",
            valid_type=Str,
            default=lambda: Str("1/cm"),
            help="Unit for `energy_spacing`, `energy_max` and `final_energy`.",
        )
        spec.input(
            "detector_angles",
            valid_type=List,
            default=lambda: List(list=[135.0, 45.0]),
            help="Scattering angles in degrees, one per detector bank to evaluate.",
        )
        spec.input(
            "final_energy",
            valid_type=Float,
            default=lambda: Float(32.0),
            help="Analyser-fixed final neutron energy, in `energy_unit`.",
        )
        spec.input(
            "resolution_model",
            valid_type=Str,
            default=lambda: Str("AbINS_v1"),
            help="Name of the resins resolution model applied when broadening.",
        )
        spec.input(
            "group_by",
            valid_type=List,
            default=lambda: List(list=[]),
            help=(
                "Metadata keys to group and sum spectrum lines by (e.g. "
                "['atom_symbol'], ['quantum_order'], or both). Empty (the "
                "default) yields a single total spectrum."
            ),
        )
        spec.outline(
            cls.compute_intensities,
            cls.group,
            cls.broaden,
            cls.finalize,
        )
        spec.output(
            "components",
            valid_type=XyData,
            help=(
                "The full, ungrouped line set: one line per contributing atom, "
                "quantum order and detector angle. Committed to the graph before "
                "grouping so that regrouping can reuse this calculation."
            ),
        )
        spec.output(
            "spectrum",
            valid_type=XyData,
            help="The grouped and resolution-broadened TOSCA spectrum.",
        )
        spec.exit_code(
            400,
            "ERROR_SUB_PROCESS_FAILED",
            message="The intensity PythonJob did not finish successfully.",
        )

    def compute_intensities(self):
        """Compute the full, ungrouped line set as a PythonJob."""
        inputs = prepare_tosca_spectrum_inputs(
            self.inputs.modes,
            temperature=self.inputs.temperature.value,
            energy_spacing=self.inputs.energy_spacing.value,
            energy_max=self.inputs.energy_max.value,
            detector_angles=self.inputs.detector_angles.get_list(),
            final_energy=self.inputs.final_energy.value,
            energy_unit=self.inputs.energy_unit.value,
            code=self.inputs.code,
            metadata=self.get_job_metadata(),
        )
        return ToContext(intensities=self.submit(PythonJob, **inputs))

    def group(self):
        """Group the committed line set by the requested metadata keys."""
        if not self.ctx.intensities.is_finished_ok:
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED
        self.ctx.components = self.ctx.intensities.outputs.result
        self.ctx.grouped = group_spectra(self.ctx.components, self.inputs.group_by)
        return None

    def broaden(self):
        """Apply resolution broadening to the grouped spectrum."""
        self.ctx.spectrum = broaden_spectra(
            self.ctx.grouped, self.inputs.resolution_model
        )

    def finalize(self) -> ExitCode | None:
        """Expose the ungrouped components and the grouped, broadened spectrum."""
        self.out("components", self.ctx.components)
        self.out("spectrum", self.ctx.spectrum)


class ToscaFromForceConstantsWorkChain(
    FromForceConstantsWorkChain, JobDispatchWorkChain
):
    """Compute a TOSCA spectrum from force constants, via interpolated modes.

    Resolves force constants by running
    :class:`~aiida_alc_ins.workflows.force_constants.ForceConstantsWorkChain`
    as a sub-workflow (a CASTEP file, read in-process by the
    ``read_castep_force_constants`` calcfunction, or a prepared node -- exactly
    one, as usual), interpolates modes on a Monkhorst-Pack grid (a powder
    average, matching :class:`~aiida_alc_ins.workflows.dos.DosWorkChain`
    rather than the symmetry-path sampling of
    :class:`~aiida_alc_ins.workflows.dispersion.DispersionWorkChain`: the
    almost-isotropic incoherent approximation needs a representative *density*
    of modes, not specific q-point positions), and delegates the spectrum
    calculation to :class:`ToscaFromModesWorkChain` rather than reimplementing
    it, so the intensity calculation stays reusable.

    Exit Codes:
        * 400 (ERROR_SUB_PROCESS_FAILED): A PythonJob step of this workflow's own
          (the mode interpolation) did not finish successfully.
        * 401 (ERROR_SPECTRUM_WORKCHAIN_FAILED): The delegated
          ``ToscaFromModesWorkChain`` did not finish successfully.
        * 402 (ERROR_SUB_PROCESS_FAILED_FORCE_CONSTANTS): The
          ``ForceConstantsWorkChain`` sub-workflow did not finish successfully.
    """

    @classmethod
    def define(cls, spec) -> None:
        super().define(spec)  # force_constants namespace + code/options + exit codes
        spec.input(
            "q_spacing",
            valid_type=Float,
            default=lambda: Float(0.1),
            help=(
                "Target Monkhorst-Pack grid spacing for the mode sampling, "
                "in 1/Angstrom."
            ),
        )
        spec.expose_inputs(
            ToscaFromModesWorkChain,
            namespace="spectrum",
            exclude=("modes", "code"),
            namespace_options={
                "help": (
                    "Scientific and instrument inputs forwarded to the composed "
                    "ToscaFromModesWorkChain (modes and code excluded: modes is "
                    "produced internally, and code is provided at the top level "
                    "for this workflow's own mode-interpolation step)."
                )
            },
        )
        spec.outline(
            cls.run_force_constants,
            cls.inspect_force_constants,
            cls.interpolate_modes,
            cls.compute_spectrum,
            cls.finalize,
        )
        spec.expose_outputs(ToscaFromModesWorkChain)
        spec.exit_code(
            401,
            "ERROR_SPECTRUM_WORKCHAIN_FAILED",
            message=(
                "The delegated ToscaFromModesWorkChain did not finish successfully."
            ),
        )

    def interpolate_modes(self):
        """Interpolate phonon modes on a Monkhorst-Pack grid, as a PythonJob."""
        inputs = prepare_grid_interpolation_inputs(
            self.ctx.force_constants,
            q_spacing=self.inputs.q_spacing.value,
            code=self.inputs.code,
            metadata=self.get_job_metadata(),
        )
        return ToContext(modes=self.submit(PythonJob, **inputs))

    def compute_spectrum(self) -> ToContext | ExitCode | None:
        """Delegate the spectrum calculation to ToscaFromModesWorkChain."""
        if not self.ctx.modes.is_finished_ok:
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED

        inputs = AttributeDict(
            self.exposed_inputs(ToscaFromModesWorkChain, namespace="spectrum")
        )
        inputs.modes = self.ctx.modes.outputs.result
        inputs.code = self.inputs.code
        if "options" in self.inputs and "options" not in inputs:
            inputs.options = self.inputs.options
        return ToContext(
            spectrum_workchain=self.submit(ToscaFromModesWorkChain, **inputs)
        )

    def finalize(self) -> ExitCode | None:
        """Expose the delegated workchain's outputs as this chain's own."""
        workchain = self.ctx.spectrum_workchain
        if not workchain.is_finished_ok:
            return self.exit_codes.ERROR_SPECTRUM_WORKCHAIN_FAILED
        self.out_many(self.exposed_outputs(workchain, ToscaFromModesWorkChain))
        return None
