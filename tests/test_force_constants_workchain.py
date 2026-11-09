"""Tests for the standalone :class:`ForceConstantsWorkChain`.

These tests deliberately use no ``Code`` fixture: the workflow dispatches no
jobs and takes no ``code`` or ``options`` input.
"""

from __future__ import annotations

import pytest
from aiida.engine import run_get_node
from aiida.orm import CalcFunctionNode, SinglefileData
from euphonic import ForceConstants
from tests.assertions import assert_equivalent_force_constants

from aiida_pythonjob_ins.data import ForceConstantsData
from aiida_pythonjob_ins.workflows.force_constants import ForceConstantsWorkChain


def test_spec_has_no_code_or_options():
    """The spec offers neither a ``code`` nor an ``options`` input."""
    inputs = ForceConstantsWorkChain.spec().inputs
    assert "code" not in inputs
    assert "options" not in inputs


def test_castep_file_gives_equivalent_force_constants(quartz_castep_bin):
    """A CASTEP file is read into a ForceConstantsData equivalent to the direct read.

    The read runs as a ``CalcFunctionNode`` called by the workflow, linking the
    file to the output.
    """
    castep_file = SinglefileData(quartz_castep_bin)

    results, node = run_get_node(ForceConstantsWorkChain, castep_file=castep_file)

    assert node.is_finished_ok, node.exit_status
    assert isinstance(results["force_constants"], ForceConstantsData)

    # The read appears as a CalcFunctionNode called by this workflow.
    read_calcfunctions = [
        p
        for p in node.called_descendants
        if isinstance(p, CalcFunctionNode)
        and p.process_label == "read_castep_force_constants"
    ]
    assert len(read_calcfunctions) == 1
    assert read_calcfunctions[0].inputs.castep_file.uuid == castep_file.uuid

    # Equivalent to a direct public-API read on the same file.
    expected = ForceConstants.from_castep(quartz_castep_bin)
    assert_equivalent_force_constants(
        results["force_constants"].get_force_constants(), expected
    )


def test_node_is_passed_through(quartz_castep_bin):
    """A prepared node is returned with the same UUID and no called processes."""
    fc_node = ForceConstantsData(ForceConstants.from_castep(quartz_castep_bin))

    results, node = run_get_node(ForceConstantsWorkChain, node=fc_node)

    assert node.is_finished_ok, node.exit_status
    assert results["force_constants"].uuid == fc_node.uuid
    # No calculation or sub-workflow is called when a node is passed through.
    assert not list(node.called_descendants)


_EXACTLY_ONE = "exactly one of `castep_file`, `phonopy` or `node`"


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
def test_multiple_sources_rejected(quartz_castep_bin, phonopy_hdf5_nodes, sources):
    """Any combination of two or more sources raises before the run."""
    inputs = {
        "castep_file": SinglefileData(quartz_castep_bin),
        "phonopy": phonopy_hdf5_nodes,
        "node": ForceConstantsData(ForceConstants.from_castep(quartz_castep_bin)),
    }
    given = {key: inputs[key] for key in sources}
    with pytest.raises(ValueError, match=_EXACTLY_ONE):
        run_get_node(ForceConstantsWorkChain, **given)


def test_no_source_rejected():
    """Providing no source raises before the run, naming all three."""
    with pytest.raises(ValueError, match=_EXACTLY_ONE):
        run_get_node(ForceConstantsWorkChain)


def test_phonopy_files_give_equivalent_force_constants(
    phonopy_hdf5_nodes, phonopy_hdf5_reference
):
    """The ``phonopy`` source is read in one calcfunction, matching Euphonic."""
    results, node = run_get_node(ForceConstantsWorkChain, phonopy=phonopy_hdf5_nodes)

    assert node.is_finished_ok, node.exit_status
    assert_equivalent_force_constants(
        results["force_constants"].get_force_constants(), phonopy_hdf5_reference
    )
    read_calls = [
        p
        for p in node.called
        if isinstance(p, CalcFunctionNode)
        and p.process_label == "read_phonopy_force_constants"
    ]
    assert len(read_calls) == 1


def test_phonopy_without_summary_rejected(phonopy_hdf5_nodes):
    """A ``phonopy`` namespace without a summary raises before the run."""
    with pytest.raises(ValueError, match="summary"):
        run_get_node(
            ForceConstantsWorkChain, phonopy={"born": phonopy_hdf5_nodes["born"]}
        )


def test_unreadable_phonopy_exits_410_with_no_outputs(phonopy_hdf5_nodes):
    """A summary without force constants, and no separate file, ends with 410."""
    results, node = run_get_node(
        ForceConstantsWorkChain, phonopy={"summary": phonopy_hdf5_nodes["summary"]}
    )

    assert not node.is_finished_ok
    assert (
        node.exit_status == ForceConstantsWorkChain.exit_codes.ERROR_READ_FAILED.status
    )
    assert "force_constants" not in node.outputs
    assert not results


def test_junk_file_exits_410_with_no_outputs(tmp_path):
    """An unreadable file ends with ``ERROR_READ_FAILED`` (410) and no outputs.

    The outline aborts in ``read_castep_file`` before ``finalize``, so no output
    is emitted.
    """
    junk = tmp_path / "junk.castep_bin"
    junk.write_bytes(b"\x00\x01\x02 junk not castep \xff\xfe" * 100)
    castep_file = SinglefileData(junk)

    results, node = run_get_node(ForceConstantsWorkChain, castep_file=castep_file)

    assert not node.is_finished_ok
    exit_codes = ForceConstantsWorkChain.exit_codes
    assert node.exit_status == exit_codes.ERROR_READ_FAILED.status
    assert not results
    assert not list(node.outputs)
