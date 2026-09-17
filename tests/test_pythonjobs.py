"""Unit tests for PythonJob input builder helpers and metadata options handling."""

from __future__ import annotations

import numpy as np
import pytest
from aiida.orm import KpointsData, SinglefileData
from euphonic import ForceConstants

from aiida_pythonjob_ins.data import ForceConstantsData, QpointPhononModesData
from aiida_pythonjob_ins.pythonjobs import (
    prepare_dispersion_inputs,
    prepare_dos_inputs,
    prepare_grid_interpolation_inputs,
    prepare_interpolation_inputs,
    prepare_read_force_constants_inputs,
    prepare_read_phonopy_inputs,
    prepare_tosca_spectrum_inputs,
)


@pytest.fixture
def quartz_fc_node(quartz_castep_bin):
    """Fixture returning a ForceConstantsData node from CASTEP quartz data."""
    return ForceConstantsData(ForceConstants.from_castep(quartz_castep_bin))


def test_prepare_read_force_constants_inputs_metadata(quartz_castep_bin, python_code):
    """prepare_read_force_constants_inputs forwards metadata and kwargs."""
    castep_file = SinglefileData(quartz_castep_bin)
    inputs = prepare_read_force_constants_inputs(
        castep_file,
        code=python_code,
        metadata={
            "label": "read_castep",
            "options": {"resources": {"num_cpus": 1}},
        },
        process_label="CustomReadLabel",
    )
    assert "metadata" in inputs
    assert inputs["metadata"]["label"] == "read_castep"
    assert inputs["metadata"]["options"]["resources"] == {"num_cpus": 1}
    assert inputs["process_label"] == "CustomReadLabel"


def test_prepare_read_phonopy_inputs_metadata(tmp_path, python_code):
    """prepare_read_phonopy_inputs forwards metadata.options."""
    summary_file = tmp_path / "phonopy.yaml"
    summary_file.write_text("dummy phonopy")
    fc_file = tmp_path / "FORCE_CONSTANTS"
    fc_file.write_text("dummy fc")

    inputs = prepare_read_phonopy_inputs(
        SinglefileData(summary_file),
        SinglefileData(fc_file),
        code=python_code,
        metadata={"options": {"resources": {"num_cpus": 2}}},
    )
    assert inputs["metadata"]["options"]["resources"] == {"num_cpus": 2}


def test_prepare_dos_inputs_metadata(quartz_fc_node, python_code):
    """prepare_dos_inputs forwards metadata.options."""
    inputs = prepare_dos_inputs(
        quartz_fc_node,
        code=python_code,
        metadata={"options": {"resources": {"num_cpus": 4}, "queue_name": "compute"}},
    )
    assert inputs["metadata"]["options"]["resources"] == {"num_cpus": 4}
    assert inputs["metadata"]["options"]["queue_name"] == "compute"


def test_prepare_dispersion_inputs_metadata(quartz_fc_node, python_code):
    """prepare_dispersion_inputs forwards metadata.options."""
    inputs = prepare_dispersion_inputs(
        quartz_fc_node,
        code=python_code,
        metadata={"options": {"resources": {"num_cpus": 1}}},
    )
    assert inputs["metadata"]["options"]["resources"] == {"num_cpus": 1}


def test_prepare_interpolation_inputs_metadata(quartz_fc_node, python_code):
    """prepare_interpolation_inputs forwards metadata.options."""
    kpoints = KpointsData()
    kpoints.set_kpoints([[0.0, 0.0, 0.0]])
    inputs = prepare_interpolation_inputs(
        quartz_fc_node,
        kpoints,
        code=python_code,
        metadata={"options": {"resources": {"num_cpus": 2}}},
    )
    assert inputs["metadata"]["options"]["resources"] == {"num_cpus": 2}


def test_prepare_grid_interpolation_inputs_metadata(quartz_fc_node, python_code):
    """prepare_grid_interpolation_inputs forwards metadata.options."""
    inputs = prepare_grid_interpolation_inputs(
        quartz_fc_node,
        code=python_code,
        metadata={"options": {"resources": {"num_cpus": 1}}},
    )
    assert inputs["metadata"]["options"]["resources"] == {"num_cpus": 1}


def test_prepare_tosca_spectrum_inputs_metadata(quartz_fc_node, python_code):
    """prepare_tosca_spectrum_inputs forwards metadata.options."""
    fc = quartz_fc_node.get_force_constants()
    modes = QpointPhononModesData(
        fc.calculate_qpoint_phonon_modes(np.array([[0.0, 0.0, 0.0]]))
    )
    inputs = prepare_tosca_spectrum_inputs(
        modes,
        code=python_code,
        metadata={"options": {"resources": {"num_cpus": 1}}},
    )
    assert inputs["metadata"]["options"]["resources"] == {"num_cpus": 1}
