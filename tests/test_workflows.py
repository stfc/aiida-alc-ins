"""End-to-end tests for the WorkChains."""

from __future__ import annotations

import struct
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from aiida.engine import run_get_node
from aiida.manage.caching import enable_caching
from aiida.orm import (
    BandsData,
    CalcFunctionNode,
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
from tests.assertions import assert_equivalent_force_constants

from aiida_pythonjob_ins.data import ForceConstantsData, QpointPhononModesData
from aiida_pythonjob_ins.workflows import (
    DispersionWorkChain,
    DosWorkChain,
    ForceConstantsWorkChain,
    ToscaFromForceConstantsWorkChain,
    ToscaFromModesWorkChain,
)
from aiida_pythonjob_ins.workflows.force_constants import (
    read_castep_force_constants,
    read_phonopy_force_constants,
)
from aiida_pythonjob_ins.workflows.tosca import group_spectra

# The process_type aiida-pythonjob registers PythonJob under -- see
# `PythonJob.build_process_type()` -- needed as the `enable_caching` identifier
# since it differs from the class's own dotted Python path.
_PYTHONJOB_PROCESS_TYPE = "aiida.calculations:pythonjob.pythonjob"


# --- read_castep_force_constants calcfunction -------------------------------


def test_read_castep_force_constants_valid(quartz_castep_bin):
    """A valid file yields a ForceConstantsData equivalent to the direct read.

    Runs without a ``Code`` or ``Computer`` fixture -- the calcfunction is
    in-process. The returned node is linked to the input ``SinglefileData`` via a
    ``CalcFunctionNode``.
    """
    castep_file = SinglefileData(quartz_castep_bin)
    result, node = run_get_node(read_castep_force_constants, castep_file=castep_file)

    assert node.is_finished_ok, node.exit_status
    assert isinstance(result, ForceConstantsData)
    assert isinstance(node, CalcFunctionNode)
    # The CalcFunctionNode links the input file to its output.
    assert "castep_file" in node.inputs
    assert node.inputs.castep_file.uuid == castep_file.uuid
    assert "result" in node.outputs

    # Equivalent to a direct public-API read on the same file.
    expected = ForceConstants.from_castep(quartz_castep_bin)
    assert_equivalent_force_constants(result.get_force_constants(), expected)


def test_read_castep_force_constants_junk(tmp_path):
    """A junk file finishes with exit status 300, a named cause, and no outputs."""
    junk = tmp_path / "junk.castep_bin"
    junk.write_bytes(b"\x00\x01\x02 junk not castep \xff\xfe" * 100)
    castep_file = SinglefileData(junk)

    result, node = run_get_node(read_castep_force_constants, castep_file=castep_file)

    assert not node.is_finished_ok
    assert node.exit_status == 300
    assert node.exit_message is not None
    assert "Could not read CASTEP force constants" in node.exit_message
    # No outputs are emitted on failure.
    assert not result
    assert not list(node.outputs)


@pytest.mark.parametrize("n_bytes", [1, 3], ids=["1-byte", "3-byte"])
def test_read_castep_force_constants_truncated(tmp_path, n_bytes):
    """A file truncated under 4 bytes exits 300 (struct.error)."""
    truncated = tmp_path / "truncated.castep_bin"
    truncated.write_bytes(b"\x00" * n_bytes)
    castep_file = SinglefileData(truncated)

    result, node = run_get_node(read_castep_force_constants, castep_file=castep_file)

    assert not node.is_finished_ok
    assert node.exit_status == 300
    assert node.exit_message is not None
    assert "Could not read CASTEP force constants" in node.exit_message
    assert not result
    assert not list(node.outputs)


def test_read_castep_force_constants_mismatched_markers(tmp_path):
    """A file with mismatched Fortran record markers exits 300 (OSError)."""
    corrupt = tmp_path / "mismatched.castep_bin"
    # begin marker says 8 bytes of data; end marker says 4 -- they don't match.
    corrupt.write_bytes(struct.pack(">i", 8) + b"\x00" * 8 + struct.pack(">i", 4))
    castep_file = SinglefileData(corrupt)

    result, node = run_get_node(read_castep_force_constants, castep_file=castep_file)

    assert not node.is_finished_ok
    assert node.exit_status == 300
    assert node.exit_message is not None
    assert "Could not read CASTEP force constants" in node.exit_message
    assert not result
    assert not list(node.outputs)


def test_read_castep_force_constants_missing_force_constants(tmp_path):
    """A valid CASTEP file lacking force constants exits 300 (RuntimeError).

    Euphonic raises ``RuntimeError`` with "Force constants matrix could not be
    found" when the ``FORCE_CON`` block is absent. The calcfunction catches this
    by message and returns an ``ExitCode`` rather than excepting.
    """
    dummy = tmp_path / "dummy.castep_bin"
    dummy.write_bytes(b"\x00" * 4)  # content irrelevant; from_castep is mocked
    castep_file = SinglefileData(dummy)

    with patch.object(
        ForceConstantsData,
        "from_castep",
        side_effect=RuntimeError(
            "Invalid file (dummy). Force constants matrix could not be found"
        ),
    ):
        result, node = run_get_node(
            read_castep_force_constants, castep_file=castep_file
        )

    assert not node.is_finished_ok
    assert node.exit_status == 300
    assert node.exit_message is not None
    assert "Could not read CASTEP force constants" in node.exit_message
    assert not result
    assert not list(node.outputs)


def test_read_castep_force_constants_unrelated_runtime_error_propagates(tmp_path):
    """An unrelated RuntimeError is not caught and excepts the process.

    Only ``RuntimeError`` whose message indicates missing force constants (or an
    invalid file) is caught; genuine internal bugs propagate as Excepted.
    """
    dummy = tmp_path / "dummy.castep_bin"
    dummy.write_bytes(b"\x00" * 4)
    castep_file = SinglefileData(dummy)

    with (
        patch.object(
            ForceConstantsData,
            "from_castep",
            side_effect=RuntimeError("Something completely different"),
        ),
        pytest.raises(RuntimeError, match="Something completely different"),
    ):
        run_get_node(read_castep_force_constants, castep_file=castep_file)


# --- read_phonopy_force_constants calcfunction ------------------------------


def _phonopy_nodes(directory: Path, **names: str) -> dict[str, SinglefileData]:
    """Return ``SinglefileData`` nodes for the named files in ``directory``."""
    return {key: SinglefileData(directory / name) for key, name in names.items()}


def test_read_phonopy_force_constants_hdf5(phonopy_hdf5_dir):
    """HDF5 force constants with a Born file are read equivalently to Euphonic.

    The calcfunction links all three supplied files to its ``CalcFunctionNode``.
    """
    nodes = _phonopy_nodes(
        phonopy_hdf5_dir,
        summary="phonopy_nofc_noborn.yaml",
        force_constants="force_constants.hdf5",
        born="BORN_nacl",
    )
    result, node = run_get_node(read_phonopy_force_constants, **nodes)

    assert node.is_finished_ok, node.exit_status
    assert isinstance(node, CalcFunctionNode)
    assert isinstance(result, ForceConstantsData)
    for key in ("summary", "force_constants", "born"):
        assert key in node.inputs

    expected = ForceConstants.from_phonopy(
        path=phonopy_hdf5_dir,
        summary_name="phonopy_nofc_noborn.yaml",
        fc_name="force_constants.hdf5",
        born_name="BORN_nacl",
    )
    assert_equivalent_force_constants(result.get_force_constants(), expected)


def test_read_phonopy_force_constants_hdf5_without_born(phonopy_hdf5_dir):
    """HDF5 force constants without a Born file yield no Born data."""
    nodes = _phonopy_nodes(
        phonopy_hdf5_dir,
        summary="phonopy_nofc_noborn.yaml",
        force_constants="force_constants.hdf5",
    )
    result, node = run_get_node(read_phonopy_force_constants, **nodes)

    assert node.is_finished_ok, node.exit_status
    expected = ForceConstants.from_phonopy(
        path=phonopy_hdf5_dir,
        summary_name="phonopy_nofc_noborn.yaml",
        fc_name="force_constants.hdf5",
    )
    got = result.get_force_constants()
    assert_equivalent_force_constants(got, expected)
    assert got.born is None


def test_read_phonopy_force_constants_text_format(phonopy_dir):
    """Phonopy text-format force constants are read equivalently to Euphonic."""
    nodes = _phonopy_nodes(
        phonopy_dir,
        summary="phonopy.yaml",
        force_constants="FORCE_CONSTANTS",
        born="BORN",
    )
    result, node = run_get_node(read_phonopy_force_constants, **nodes)

    assert node.is_finished_ok, node.exit_status
    expected = ForceConstants.from_phonopy(
        path=phonopy_dir,
        summary_name="phonopy.yaml",
        fc_name="FORCE_CONSTANTS",
        born_name="BORN",
    )
    assert_equivalent_force_constants(result.get_force_constants(), expected)


def test_read_phonopy_force_constants_embedded_summary(phonopy_hdf5_dir):
    """A summary that embeds force constants needs no ``force_constants`` file."""
    nodes = _phonopy_nodes(phonopy_hdf5_dir, summary="phonopy_nacl.yaml")
    result, node = run_get_node(read_phonopy_force_constants, **nodes)

    assert node.is_finished_ok, node.exit_status
    expected = ForceConstants.from_phonopy(
        path=phonopy_hdf5_dir, summary_name="phonopy_nacl.yaml"
    )
    assert_equivalent_force_constants(result.get_force_constants(), expected)


def test_read_phonopy_force_constants_missing_force_constants(phonopy_hdf5_dir):
    """A summary without force constants and no ``force_constants`` file exits 300."""
    nodes = _phonopy_nodes(phonopy_hdf5_dir, summary="phonopy_nofc_noborn.yaml")
    result, node = run_get_node(read_phonopy_force_constants, **nodes)

    assert not node.is_finished_ok
    assert node.exit_status == 300
    assert node.exit_message is not None
    assert "Could not read Phonopy force constants" in node.exit_message
    assert not result
    assert not list(node.outputs)


def test_read_phonopy_force_constants_corrupt_hdf5(phonopy_hdf5_dir, tmp_path):
    """Junk bytes in an HDF5 force-constants file exit 300 with no outputs."""
    corrupt = tmp_path / "force_constants.hdf5"
    corrupt.write_bytes(b"\x00\x01 not hdf5 \xff" * 100)
    nodes = {
        "summary": SinglefileData(phonopy_hdf5_dir / "phonopy_nofc_noborn.yaml"),
        "force_constants": SinglefileData(corrupt),
    }
    result, node = run_get_node(read_phonopy_force_constants, **nodes)

    assert not node.is_finished_ok
    assert node.exit_status == 300
    assert node.exit_message is not None
    assert "Could not read Phonopy force constants" in node.exit_message
    assert not result
    assert not list(node.outputs)


def test_read_phonopy_force_constants_unrelated_error_propagates(
    phonopy_hdf5_dir,
):
    """An error outside ``PHONOPY_READ_ERRORS`` is not caught; the process excepts."""
    nodes = _phonopy_nodes(phonopy_hdf5_dir, summary="phonopy_nacl.yaml")
    with (
        patch.object(
            ForceConstantsData,
            "from_phonopy",
            side_effect=RuntimeError("Something completely different"),
        ),
        pytest.raises(RuntimeError, match="Something completely different"),
    ):
        run_get_node(read_phonopy_force_constants, **nodes)


def test_dispersion_workchain(python_code, quartz_castep_bin):
    """Read force constants -> q-point path -> modes -> band structure.

    Checks the native-type outputs (KpointsData path, BandsData) and that the
    workflow is orchestrated as one provenance graph. The force-constants source
    is resolved by a ``ForceConstantsWorkChain`` sub-workflow, whose read step is
    an in-process calcfunction (one ``CalcFunctionNode``), not a dispatched
    PythonJob.
    """
    castep_file = SinglefileData(quartz_castep_bin)

    results, node = run_get_node(
        DispersionWorkChain,
        force_constants={"castep_file": castep_file},
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

    # Exactly one ForceConstantsWorkChain is called as a sub-workflow.
    fc_workchains = [
        p
        for p in node.called_descendants
        if isinstance(p, WorkChainNode) and p.process_label == "ForceConstantsWorkChain"
    ]
    assert len(fc_workchains) == 1
    # Its output feeds the next step: the interpolation PythonJob consumes the
    # force constants the sub-workflow produced.
    calcjobs = [p for p in node.called_descendants if isinstance(p, CalcJobNode)]
    assert len(calcjobs) == 1
    assert (
        calcjobs[0].inputs.function_inputs.force_constants.uuid
        == fc_workchains[0].outputs.force_constants.uuid
    )

    # The read is one in-process calcfunction, called by the ForceConstantsWorkChain
    # child -- not by this consumer directly.
    read_calcfunctions = [
        p
        for p in node.called_descendants
        if isinstance(p, CalcFunctionNode)
        and p.process_label == "read_castep_force_constants"
    ]
    assert len(read_calcfunctions) == 1
    assert read_calcfunctions[0].inputs.castep_file.uuid == castep_file.uuid
    assert read_calcfunctions[0].caller.uuid == fc_workchains[0].uuid

    # Only the interpolation PythonJob is dispatched; the read and band-structure
    # steps are calcfunctions, not CalcJobs.
    calcjobs = [p for p in node.called_descendants if isinstance(p, CalcJobNode)]
    assert len(calcjobs) == 1


def test_dos_workchain(python_code, quartz_castep_bin):
    """Read force constants -> phonon DOS as XyData with options propagation."""
    castep_file = SinglefileData(quartz_castep_bin)

    results, node = run_get_node(
        DosWorkChain,
        force_constants={"castep_file": castep_file},
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

    # Exactly one ForceConstantsWorkChain is called as a sub-workflow.
    fc_workchains = [
        p
        for p in node.called_descendants
        if isinstance(p, WorkChainNode) and p.process_label == "ForceConstantsWorkChain"
    ]
    assert len(fc_workchains) == 1

    # The read is one in-process calcfunction, called by the ForceConstantsWorkChain
    # child -- not by this consumer directly.
    read_calcfunctions = [
        p
        for p in node.called_descendants
        if isinstance(p, CalcFunctionNode)
        and p.process_label == "read_castep_force_constants"
    ]
    assert len(read_calcfunctions) == 1
    assert read_calcfunctions[0].inputs.castep_file.uuid == castep_file.uuid
    assert read_calcfunctions[0].caller.uuid == fc_workchains[0].uuid

    # Only the DOS PythonJob is dispatched (the read is a calcfunction now).
    calcjobs = [p for p in node.called_descendants if isinstance(p, CalcJobNode)]
    assert len(calcjobs) == 1
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
        force_constants={"node": _force_constants_from_phonopy(phonopy_dir)},
        q_spacing=Float(0.3),
        code=python_code,
    )
    assert node.is_finished_ok, node.exit_status
    assert isinstance(results["band_structure"], BandsData)
    # Exactly one ForceConstantsWorkChain is called, even for a node source.
    fc_workchains = [
        p
        for p in node.called_descendants
        if isinstance(p, WorkChainNode) and p.process_label == "ForceConstantsWorkChain"
    ]
    assert len(fc_workchains) == 1
    # No CASTEP read step, so only the interpolation PythonJob runs.
    calcjobs = [p for p in node.called_descendants if isinstance(p, CalcJobNode)]
    assert len(calcjobs) == 1


def test_dos_from_phonopy(python_code, phonopy_dir):
    """DosWorkChain accepts a ForceConstantsData (here from Phonopy)."""
    results, node = run_get_node(
        DosWorkChain,
        force_constants={"node": _force_constants_from_phonopy(phonopy_dir)},
        q_spacing=Float(0.5),
        energy_spacing=Float(2.0),
        code=python_code,
    )
    assert node.is_finished_ok, node.exit_status
    assert isinstance(results["dos"], XyData)


def _phonopy_hdf5_inputs(phonopy_hdf5_dir):
    """The ``phonopy`` namespace for the HDF5 NaCl set, with its Born file."""
    return _phonopy_nodes(
        phonopy_hdf5_dir,
        summary="phonopy_nofc_noborn.yaml",
        force_constants="force_constants.hdf5",
        born="BORN_nacl",
    )


def _phonopy_hdf5_force_constants(phonopy_hdf5_dir):
    """Direct Euphonic read of the HDF5 NaCl set, the reference for consumers."""
    return ForceConstants.from_phonopy(
        path=phonopy_hdf5_dir,
        summary_name="phonopy_nofc_noborn.yaml",
        fc_name="force_constants.hdf5",
        born_name="BORN_nacl",
    )


def test_dispersion_from_phonopy_files(python_code, phonopy_hdf5_dir):
    """DispersionWorkChain reads Phonopy files via its ``force_constants`` namespace."""
    results, node = run_get_node(
        DispersionWorkChain,
        force_constants={"phonopy": _phonopy_hdf5_inputs(phonopy_hdf5_dir)},
        q_spacing=Float(0.3),
        code=python_code,
    )

    assert node.is_finished_ok, node.exit_status
    assert isinstance(results["band_structure"], BandsData)
    fc_children = [
        p
        for p in node.called_descendants
        if isinstance(p, WorkChainNode) and p.process_label == "ForceConstantsWorkChain"
    ]
    assert len(fc_children) == 1
    assert_equivalent_force_constants(
        fc_children[0].outputs.force_constants.get_force_constants(),
        _phonopy_hdf5_force_constants(phonopy_hdf5_dir),
    )


def test_dos_from_phonopy_files(python_code, phonopy_hdf5_dir):
    """DosWorkChain reads Phonopy files via its ``force_constants`` namespace."""
    results, node = run_get_node(
        DosWorkChain,
        force_constants={"phonopy": _phonopy_hdf5_inputs(phonopy_hdf5_dir)},
        q_spacing=Float(0.5),
        energy_spacing=Float(2.0),
        code=python_code,
    )

    assert node.is_finished_ok, node.exit_status
    assert isinstance(results["dos"], XyData)


def test_tosca_from_force_constants_exposes_phonopy_namespace():
    """The Phonopy namespace is exposed under ``force_constants`` with its ports."""
    fc_namespace = ToscaFromForceConstantsWorkChain.spec().inputs["force_constants"]
    assert "phonopy" in fc_namespace
    assert {"summary", "force_constants", "born"} <= set(fc_namespace["phonopy"].keys())


def test_workchain_requires_exactly_one_source(python_code, quartz_castep_bin):
    """Providing both castep_file and force constants node is rejected."""
    castep_file = SinglefileData(quartz_castep_bin)
    fc_node = ForceConstantsData(ForceConstants.from_castep(quartz_castep_bin))
    with pytest.raises(ValueError, match="exactly one"):
        run_get_node(
            DispersionWorkChain,
            force_constants={"castep_file": castep_file, "node": fc_node},
            code=python_code,
        )


# --- ForceConstantsWorkChain with a Phonopy source --------------------------


def test_force_constants_workchain_from_phonopy_hdf5(phonopy_hdf5_dir):
    """The ``phonopy`` source reads HDF5 files in one calcfunction."""
    phonopy = _phonopy_nodes(
        phonopy_hdf5_dir,
        summary="phonopy_nofc_noborn.yaml",
        force_constants="force_constants.hdf5",
        born="BORN_nacl",
    )
    results, node = run_get_node(ForceConstantsWorkChain, phonopy=phonopy)

    assert node.is_finished_ok, node.exit_status
    expected = ForceConstants.from_phonopy(
        path=phonopy_hdf5_dir,
        summary_name="phonopy_nofc_noborn.yaml",
        fc_name="force_constants.hdf5",
        born_name="BORN_nacl",
    )
    assert_equivalent_force_constants(
        results["force_constants"].get_force_constants(), expected
    )
    read_calls = [
        p
        for p in node.called
        if isinstance(p, CalcFunctionNode)
        and p.process_label == "read_phonopy_force_constants"
    ]
    assert len(read_calls) == 1


@pytest.mark.parametrize(
    "sources",
    [
        ("castep_file", "phonopy"),
        ("phonopy", "node"),
        ("castep_file", "node"),
        ("castep_file", "phonopy", "node"),
    ],
    ids=["castep+phonopy", "phonopy+node", "castep+node", "all-three"],
)
def test_force_constants_workchain_rejects_multiple_sources(
    phonopy_hdf5_dir, quartz_castep_bin, sources
):
    """Any combination of two or more sources is rejected before the run."""
    inputs = {
        "castep_file": SinglefileData(quartz_castep_bin),
        "phonopy": _phonopy_nodes(
            phonopy_hdf5_dir,
            summary="phonopy_nacl.yaml",
        ),
        "node": ForceConstantsData(ForceConstants.from_castep(quartz_castep_bin)),
    }
    given = {key: inputs[key] for key in sources}
    with pytest.raises(
        ValueError, match="exactly one of `castep_file`, `phonopy` or `node`"
    ):
        run_get_node(ForceConstantsWorkChain, **given)


def test_force_constants_workchain_rejects_no_source():
    """Launching with no source is rejected, naming all three."""
    with pytest.raises(
        ValueError, match="exactly one of `castep_file`, `phonopy` or `node`"
    ):
        run_get_node(ForceConstantsWorkChain)


def test_force_constants_workchain_phonopy_requires_summary(phonopy_hdf5_dir):
    """A ``phonopy`` namespace without a summary is rejected before the run."""
    born_only = _phonopy_nodes(phonopy_hdf5_dir, born="BORN_nacl")
    with pytest.raises(ValueError, match="summary"):
        run_get_node(ForceConstantsWorkChain, phonopy=born_only)


def test_force_constants_workchain_unreadable_phonopy_exits_410(phonopy_hdf5_dir):
    """An unreadable Phonopy set ends with ``ERROR_READ_FAILED`` and no output."""
    phonopy = _phonopy_nodes(phonopy_hdf5_dir, summary="phonopy_nofc_noborn.yaml")
    results, node = run_get_node(ForceConstantsWorkChain, phonopy=phonopy)

    assert not node.is_finished_ok
    assert (
        node.exit_status == ForceConstantsWorkChain.exit_codes.ERROR_READ_FAILED.status
    )
    assert "force_constants" not in node.outputs
    assert not results


def test_force_constants_workchain_node_passthrough_ignores_empty_phonopy(
    phonopy_hdf5_dir,
):
    """A ``node`` source is passed through, and the empty ``phonopy`` is ignored.

    Guards the truthiness check in ``has_phonopy``: the ``phonopy`` key is present
    as an empty namespace when omitted.
    """
    fc_node = ForceConstantsData(
        ForceConstants.from_phonopy(
            path=phonopy_hdf5_dir,
            summary_name="phonopy_nacl.yaml",
        )
    )
    results, node = run_get_node(ForceConstantsWorkChain, node=fc_node)

    assert node.is_finished_ok, node.exit_status
    assert results["force_constants"].uuid == fc_node.uuid
    assert not node.called


def test_dispersion_read_failure_exits_402(python_code, tmp_path):
    """An unreadable CASTEP file exits 402 with no outputs and no dispatched job.

    The ``ForceConstantsWorkChain`` sub-workflow fails its read (exiting 410), and
    the consumer reports that failure with its own 402 -- distinct from 400.
    The consumer never reaches the interpolation step: no ``CalcJobNode`` is
    created and no outputs are emitted.
    """
    junk = tmp_path / "junk.castep_bin"
    junk.write_bytes(b"\x00\x01\x02 junk not castep \xff\xfe" * 100)
    castep_file = SinglefileData(junk)

    results, node = run_get_node(
        DispersionWorkChain,
        force_constants={"castep_file": castep_file},
        q_spacing=Float(0.2),
        code=python_code,
    )

    exit_codes = DispersionWorkChain.exit_codes
    assert not node.is_finished_ok
    assert (
        node.exit_status == exit_codes.ERROR_SUB_PROCESS_FAILED_FORCE_CONSTANTS.status
    )
    # 402 is distinct from the PythonJob failure code 400.
    assert node.exit_status != exit_codes.ERROR_SUB_PROCESS_FAILED.status
    # No outputs and no dispatched jobs.
    assert not results
    assert not list(node.outputs)
    calcjobs = [p for p in node.called_descendants if isinstance(p, CalcJobNode)]
    assert calcjobs == []


@pytest.mark.parametrize("n_bytes", [1, 3], ids=["1-byte", "3-byte"])
def test_dispersion_truncated_file_exits_402(python_code, tmp_path, n_bytes):
    """A sub-4-byte CASTEP file exits 402 with no outputs and no dispatched job."""
    truncated = tmp_path / "truncated.castep_bin"
    truncated.write_bytes(b"\x00" * n_bytes)
    castep_file = SinglefileData(truncated)

    results, node = run_get_node(
        DispersionWorkChain,
        force_constants={"castep_file": castep_file},
        q_spacing=Float(0.2),
        code=python_code,
    )

    exit_codes = DispersionWorkChain.exit_codes
    assert not node.is_finished_ok
    assert (
        node.exit_status == exit_codes.ERROR_SUB_PROCESS_FAILED_FORCE_CONSTANTS.status
    )
    assert not results
    assert not list(node.outputs)
    calcjobs = [p for p in node.called_descendants if isinstance(p, CalcJobNode)]
    assert calcjobs == []


def test_dispersion_mismatched_markers_exits_402(python_code, tmp_path):
    """Corrupt record markers exit 402 with no outputs and no dispatched job."""
    corrupt = tmp_path / "mismatched.castep_bin"
    corrupt.write_bytes(struct.pack(">i", 8) + b"\x00" * 8 + struct.pack(">i", 4))
    castep_file = SinglefileData(corrupt)

    results, node = run_get_node(
        DispersionWorkChain,
        force_constants={"castep_file": castep_file},
        q_spacing=Float(0.2),
        code=python_code,
    )

    exit_codes = DispersionWorkChain.exit_codes
    assert not node.is_finished_ok
    assert (
        node.exit_status == exit_codes.ERROR_SUB_PROCESS_FAILED_FORCE_CONSTANTS.status
    )
    assert not results
    assert not list(node.outputs)
    calcjobs = [p for p in node.called_descendants if isinstance(p, CalcJobNode)]
    assert calcjobs == []


@pytest.mark.parametrize("n_bytes", [1, 3], ids=["1-byte", "3-byte"])
def test_dos_truncated_file_exits_402(python_code, tmp_path, n_bytes):
    """A sub-4-byte CASTEP file exits 402 with no outputs and no dispatched job."""
    truncated = tmp_path / "truncated.castep_bin"
    truncated.write_bytes(b"\x00" * n_bytes)
    castep_file = SinglefileData(truncated)

    results, node = run_get_node(
        DosWorkChain,
        force_constants={"castep_file": castep_file},
        q_spacing=Float(0.5),
        code=python_code,
    )

    exit_codes = DosWorkChain.exit_codes
    assert not node.is_finished_ok
    assert (
        node.exit_status == exit_codes.ERROR_SUB_PROCESS_FAILED_FORCE_CONSTANTS.status
    )
    assert not results
    assert not list(node.outputs)
    calcjobs = [p for p in node.called_descendants if isinstance(p, CalcJobNode)]
    assert calcjobs == []


def test_dos_mismatched_markers_exits_402(python_code, tmp_path):
    """Corrupt record markers exit 402 with no outputs and no dispatched job."""
    corrupt = tmp_path / "mismatched.castep_bin"
    corrupt.write_bytes(struct.pack(">i", 8) + b"\x00" * 8 + struct.pack(">i", 4))
    castep_file = SinglefileData(corrupt)

    results, node = run_get_node(
        DosWorkChain,
        force_constants={"castep_file": castep_file},
        q_spacing=Float(0.5),
        code=python_code,
    )

    exit_codes = DosWorkChain.exit_codes
    assert not node.is_finished_ok
    assert (
        node.exit_status == exit_codes.ERROR_SUB_PROCESS_FAILED_FORCE_CONSTANTS.status
    )
    assert not results
    assert not list(node.outputs)
    calcjobs = [p for p in node.called_descendants if isinstance(p, CalcJobNode)]
    assert calcjobs == []


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
    # The first grouping (by atom_symbol) and the second (by quantum_order) each
    # produce a spectrum whose line count reflects the grouping key: 3 lines for
    # the distinct atom symbols (C, O, H) and 2 for fundamentals + combinations.
    assert len(node1.outputs.spectrum.get_y()) == 3  # C, O, H
    assert len(results2["spectrum"].get_y()) == 2  # fundamentals + combinations


def test_tosca_from_force_constants_workchain(python_code, quartz_castep_bin):
    """Force constants -> interpolated modes -> delegated TOSCA spectrum."""
    castep_file = SinglefileData(quartz_castep_bin)

    results, node = run_get_node(
        ToscaFromForceConstantsWorkChain,
        force_constants={"castep_file": castep_file},
        q_spacing=Float(1.0),  # coarse grid keeps the test fast
        spectrum={"energy_spacing": Float(50.0), "detector_angles": List(list=[135.0])},
        code=python_code,
    )

    assert node.is_finished_ok, node.exit_status
    assert isinstance(results["components"], XyData)
    assert isinstance(results["spectrum"], XyData)

    # Both the force-constants source and the delegated spectrum workflow appear
    # as called sub-workchains.
    sub_workchains = [
        p for p in node.called_descendants if isinstance(p, WorkChainNode)
    ]
    sub_labels = [p.process_label for p in sub_workchains]
    assert sub_labels.count("ForceConstantsWorkChain") == 1
    assert sub_labels.count("ToscaFromModesWorkChain") == 1


def test_tosca_from_force_constants_accepts_a_prepared_node(
    python_code, quartz_castep_bin
):
    """ToscaFromForceConstantsWorkChain also accepts a ForceConstantsData node."""
    fc_node = ForceConstantsData(ForceConstants.from_castep(quartz_castep_bin))

    results, node = run_get_node(
        ToscaFromForceConstantsWorkChain,
        force_constants={"node": fc_node},
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
    interpolation step.
    """

    # Quickly prepare FC outside of the workchain
    fc_node = ForceConstantsData(ForceConstants.from_castep(quartz_castep_bin))

    _, node = run_get_node(
        ToscaFromForceConstantsWorkChain,
        force_constants={"node": fc_node},
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
