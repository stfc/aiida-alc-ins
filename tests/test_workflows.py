"""End-to-end tests for the WorkChains."""

from __future__ import annotations

import numpy as np
import pytest
from aiida.engine import run_get_node
from aiida.manage.caching import enable_caching
from aiida.orm import (
    BandsData,
    CalcJobNode,
    Dict,
    Float,
    KpointsData,
    List,
    SinglefileData,
    StructureData,
    WorkChainNode,
    XyData,
)
from euphonic import ForceConstants, QpointPhononModes

from aiida_pythonjob_ins.data import ForceConstantsData, QpointPhononModesData
from aiida_pythonjob_ins.workflows import (
    DispersionWorkChain,
    DosWorkChain,
    ToscaFromForceConstantsWorkChain,
    ToscaFromModesWorkChain,
)
from aiida_pythonjob_ins.workflows.tosca import group_spectra

# The process_type aiida-pythonjob registers PythonJob under -- see
# `PythonJob.build_process_type()` -- needed as the `enable_caching` identifier
# since it differs from the class's own dotted Python path.
_PYTHONJOB_PROCESS_TYPE = "aiida.calculations:pythonjob.pythonjob"


def test_dispersion_workchain(python_code, quartz_castep_bin):
    """Read force constants -> q-point path -> modes -> band structure.

    Checks the native-type outputs (KpointsData path, BandsData) and that the
    three PythonJob steps were orchestrated as one provenance graph.
    """
    castep_file = SinglefileData(quartz_castep_bin)

    results, node = run_get_node(
        DispersionWorkChain,
        castep_file=castep_file,
        q_spacing=Float(0.2),  # coarse spacing keeps the test fast
        code=python_code,
    )

    assert node.is_finished_ok, node.exit_status

    modes_node = results["phonon_modes"]
    structure = results["structure"]
    band_path = results["band_path"]
    band_structure = results["band_structure"]
    assert isinstance(modes_node, QpointPhononModesData)
    assert isinstance(structure, StructureData)
    assert isinstance(band_path, KpointsData)
    assert isinstance(band_structure, BandsData)

    # The band path carries high-symmetry labels (e.g. Gamma).
    assert band_path.labels, "expected labelled high-symmetry points"

    # BandsData bands come from the phonon frequencies: shapes must line up with
    # the q-point path and the number of phonon branches.
    modes = modes_node.get_modes()
    n_branches = modes.crystal.n_atoms * 3
    bands = band_structure.get_bands()
    assert bands.shape == (modes.frequencies.shape[0], n_branches)
    assert band_path.get_kpoints().shape[0] == bands.shape[0]

    # Two PythonJob CalcJobs (read + interpolate) were orchestrated; the band path
    # and band-structure steps are calcfunctions, not CalcJobs.
    calcjobs = [p for p in node.called_descendants if isinstance(p, CalcJobNode)]
    assert len(calcjobs) == 2


def test_dos_workchain(python_code, quartz_castep_bin):
    """Read force constants -> phonon DOS as XyData with options propagation."""
    castep_file = SinglefileData(quartz_castep_bin)

    results, node = run_get_node(
        DosWorkChain,
        castep_file=castep_file,
        q_spacing=Float(0.5),  # coarse grid keeps the test fast
        energy_spacing=Float(2.0),
        code=python_code,
        options={
            "resources": {"num_machines": 1, "num_mpiprocs_per_machine": 1},
            "max_wallclock_seconds": 3600,
        },
    )

    assert node.is_finished_ok, node.exit_status
    dos = results["dos"]
    assert isinstance(dos, XyData)
    _, energy, _ = dos.get_x()
    ((_, values, _),) = dos.get_y()
    assert len(energy) == len(values)
    assert (values >= 0).all()

    # Options are recorded in provenance and propagated to child PythonJobs
    assert "options" in node.inputs
    assert isinstance(node.inputs.options, Dict)
    assert node.inputs.options.get_dict()["max_wallclock_seconds"] == 3600

    # read + dos, both PythonJobs
    calcjobs = [p for p in node.called_descendants if isinstance(p, CalcJobNode)]
    assert len(calcjobs) == 2
    for calcjob in calcjobs:
        opts = calcjob.get_options()
        assert opts["resources"] == {
            "num_machines": 1,
            "num_mpiprocs_per_machine": 1,
        }
        assert opts["max_wallclock_seconds"] == 3600


def _force_constants_from_phonopy(phonopy_dir):
    fc = ForceConstants.from_phonopy(
        path=str(phonopy_dir),
        summary_name="phonopy.yaml",
        fc_name="FORCE_CONSTANTS",
        born_name="BORN",
    )
    return ForceConstantsData(fc)


def test_dispersion_from_phonopy(python_code, phonopy_dir):
    """DispersionWorkChain accepts a ForceConstantsData (here from Phonopy)."""
    results, node = run_get_node(
        DispersionWorkChain,
        force_constants=_force_constants_from_phonopy(phonopy_dir),
        q_spacing=Float(0.3),
        code=python_code,
    )
    assert node.is_finished_ok, node.exit_status
    assert isinstance(results["band_structure"], BandsData)
    # No CASTEP read step, so only the interpolation PythonJob runs.
    calcjobs = [p for p in node.called_descendants if isinstance(p, CalcJobNode)]
    assert len(calcjobs) == 1


def test_dos_from_phonopy(python_code, phonopy_dir):
    """DosWorkChain accepts a ForceConstantsData (here from Phonopy)."""
    results, node = run_get_node(
        DosWorkChain,
        force_constants=_force_constants_from_phonopy(phonopy_dir),
        q_spacing=Float(0.5),
        energy_spacing=Float(2.0),
        code=python_code,
    )
    assert node.is_finished_ok, node.exit_status
    assert isinstance(results["dos"], XyData)


def test_workchain_requires_exactly_one_source(python_code, quartz_castep_bin):
    """Providing both castep_file and force_constants is rejected."""
    castep_file = SinglefileData(quartz_castep_bin)
    fc_node = ForceConstantsData(ForceConstants.from_castep(quartz_castep_bin))
    with pytest.raises(ValueError, match="exactly one"):
        run_get_node(
            DispersionWorkChain,
            castep_file=castep_file,
            force_constants=fc_node,
            code=python_code,
        )


# --- ToscaFromModesWorkChain / ToscaFromForceConstantsWorkChain ---------------


def test_tosca_from_modes_workchain(python_code, ethanol_modes_json):
    """Modes -> full line set + grouped, broadened TOSCA spectrum."""
    modes_node = QpointPhononModesData.from_json_file(ethanol_modes_json)

    results, node = run_get_node(
        ToscaFromModesWorkChain,
        modes=modes_node,
        energy_spacing=Float(50.0),
        detector_angles=List(list=[135.0, 45.0]),
        code=python_code,
    )

    assert node.is_finished_ok, node.exit_status
    components = results["components"]
    spectrum = results["spectrum"]
    assert isinstance(components, XyData)
    assert isinstance(spectrum, XyData)

    modes = QpointPhononModes.from_json_file(ethanol_modes_json)
    # One component line per (atom, quantum order, detector bank).
    assert len(components.get_y()) == modes.crystal.n_atoms * 2 * 2
    # Default group_by is empty -> a single total line.
    ((_, spectrum_values, _),) = spectrum.get_y()
    assert np.isfinite(spectrum_values).all()
    assert (spectrum_values >= 0).all()

    # Only one PythonJob (the intensity calculation); grouping/broadening are
    # cheap calcfunctions, not dispatched.
    calcjobs = [p for p in node.called_descendants if isinstance(p, CalcJobNode)]
    assert len(calcjobs) == 1


def test_tosca_from_modes_grouping_changes_line_count(python_code, ethanol_modes_json):
    """Different group_by keys change the number of lines in `spectrum`."""
    modes_node = QpointPhononModesData.from_json_file(ethanol_modes_json)

    _, node_by_symbol = run_get_node(
        ToscaFromModesWorkChain,
        modes=modes_node,
        energy_spacing=Float(50.0),
        detector_angles=List(list=[135.0]),
        group_by=List(list=["atom_symbol"]),
        code=python_code,
    )
    assert node_by_symbol.is_finished_ok, node_by_symbol.exit_status
    by_symbol = node_by_symbol.outputs.spectrum
    assert len(by_symbol.get_y()) == 3  # C, O, H

    _, node_by_order = run_get_node(
        ToscaFromModesWorkChain,
        modes=modes_node,
        energy_spacing=Float(50.0),
        detector_angles=List(list=[135.0]),
        group_by=List(list=["quantum_order"]),
        code=python_code,
    )
    assert node_by_order.is_finished_ok, node_by_order.exit_status
    by_order = node_by_order.outputs.spectrum
    assert len(by_order.get_y()) == 2  # fundamentals + combinations


def test_tosca_from_modes_grouped_intensity_is_conserved(
    python_code, ethanol_modes_json
):
    """Summing the grouped output equals summing the ungrouped output.

    Checked against the workflow's own `group_spectra` step directly (before
    broadening), since the exposed `spectrum` output is also broadened, and
    resins' resolution kernel is only area-, not discrete-sum-, preserving
    (truncated at the mesh edges) -- comparing after broadening would be
    checking the wrong property.
    """
    modes_node = QpointPhononModesData.from_json_file(ethanol_modes_json)

    results, node = run_get_node(
        ToscaFromModesWorkChain,
        modes=modes_node,
        energy_spacing=Float(50.0),
        detector_angles=List(list=[135.0]),
        group_by=List(list=["atom_symbol"]),
        code=python_code,
    )
    assert node.is_finished_ok, node.exit_status

    grouped = group_spectra(results["components"], List(list=["atom_symbol"]))

    ungrouped_total = sum(values for _, values, _ in results["components"].get_y())
    grouped_total = sum(values for _, values, _ in grouped.get_y())
    np.testing.assert_allclose(grouped_total, ungrouped_total)


def test_tosca_from_modes_has_no_sampling_parameter():
    """The modes-based workflow declares no q-point sampling parameter.

    That parameter belongs only to `ToscaFromForceConstantsWorkChain`, which
    samples q-points from force constants before delegating here.
    """
    assert "q_spacing" not in ToscaFromModesWorkChain.spec().inputs


def test_tosca_from_modes_regrouping_reuses_the_cached_intensities(
    python_code, ethanol_modes_json
):
    """A second run differing only in group_by reuses the intensity PythonJob."""
    modes_node = QpointPhononModesData.from_json_file(ethanol_modes_json)

    with enable_caching(identifier=_PYTHONJOB_PROCESS_TYPE):
        _, node1 = run_get_node(
            ToscaFromModesWorkChain,
            modes=modes_node,
            energy_spacing=Float(50.0),
            detector_angles=List(list=[135.0]),
            group_by=List(list=["atom_symbol"]),
            code=python_code,
        )
        assert node1.is_finished_ok, node1.exit_status

        results2, node2 = run_get_node(
            ToscaFromModesWorkChain,
            modes=modes_node,
            energy_spacing=Float(50.0),
            detector_angles=List(list=[135.0]),
            group_by=List(list=["quantum_order"]),
            code=python_code,
        )
        assert node2.is_finished_ok, node2.exit_status

    calcjobs2 = [p for p in node2.called_descendants if isinstance(p, CalcJobNode)]
    assert len(calcjobs2) == 1
    assert calcjobs2[0].base.caching.is_created_from_cache
    # The newly grouped result is still produced and provenance-linked.
    assert len(results2["spectrum"].get_y()) == 2  # fundamentals + combinations


def test_tosca_from_force_constants_workchain(python_code, quartz_castep_bin):
    """Force constants -> interpolated modes -> delegated TOSCA spectrum."""
    castep_file = SinglefileData(quartz_castep_bin)

    results, node = run_get_node(
        ToscaFromForceConstantsWorkChain,
        castep_file=castep_file,
        q_spacing=Float(1.0),  # coarse grid keeps the test fast
        spectrum={"energy_spacing": Float(50.0), "detector_angles": List(list=[135.0])},
        code=python_code,
    )

    assert node.is_finished_ok, node.exit_status
    assert isinstance(results["components"], XyData)
    assert isinstance(results["spectrum"], XyData)

    # The delegated modes-based workflow is a called sub-workflow, with the
    # interpolated modes linking the two.
    sub_workchains = [
        p for p in node.called_descendants if isinstance(p, WorkChainNode)
    ]
    assert len(sub_workchains) == 1
    assert sub_workchains[0].process_label == "ToscaFromModesWorkChain"


def test_tosca_from_force_constants_accepts_a_prepared_node(
    python_code, quartz_castep_bin
):
    """ToscaFromForceConstantsWorkChain also accepts a ForceConstantsData node."""
    fc_node = ForceConstantsData(ForceConstants.from_castep(quartz_castep_bin))

    results, node = run_get_node(
        ToscaFromForceConstantsWorkChain,
        force_constants=fc_node,
        q_spacing=Float(1.0),
        spectrum={"energy_spacing": Float(50.0), "detector_angles": List(list=[135.0])},
        code=python_code,
    )

    assert node.is_finished_ok, node.exit_status
    assert isinstance(results["spectrum"], XyData)
    # No CASTEP read step, so only the interpolation PythonJob runs directly
    # under this workflow (the intensity PythonJob runs under the sub-workchain).
    own_calcjobs = [
        p
        for p in node.called_descendants
        if isinstance(p, CalcJobNode) and p.caller.uuid == node.uuid
    ]
    assert len(own_calcjobs) == 1


def test_tosca_from_force_constants_failure_is_distinguishable(
    python_code, quartz_castep_bin
):
    """A failure of the delegated workflow returns a distinct exit code.

    Simulated by requesting an energy_max so small that no positive-energy bin
    survives clipping, which starves the intensity calculation of any bins and
    fails the sub-workchain's PythonJob rather than this workflow's own
    force-constants step.
    """
    castep_file = SinglefileData(quartz_castep_bin)

    _, node = run_get_node(
        ToscaFromForceConstantsWorkChain,
        castep_file=castep_file,
        q_spacing=Float(1.0),
        spectrum={
            "energy_spacing": Float(50.0),
            "energy_max": Float(0.0),
            "detector_angles": List(list=[135.0]),
        },
        code=python_code,
    )

    exit_codes = ToscaFromForceConstantsWorkChain.exit_codes
    assert not node.is_finished_ok
    assert node.exit_status == exit_codes.ERROR_SPECTRUM_WORKCHAIN_FAILED.status
    assert node.exit_status != exit_codes.ERROR_SUB_PROCESS_FAILED.status
