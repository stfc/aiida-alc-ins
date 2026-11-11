"""Round-trip tests for the custom Euphonic Data nodes.

These verify that storing a Euphonic object in an AiiDA node and reading it back
(after a store/reload cycle) reproduces the original object.
"""

from __future__ import annotations

import numpy as np
import pytest
from aiida.orm import StructureData
from euphonic import ForceConstants
from tests.assertions import assert_equivalent_force_constants

from aiida_alc_ins.data import (
    EuphonicCrystalData,
    ForceConstantsData,
    QpointPhononModesData,
)


def test_force_constants_roundtrip(aiida_profile, quartz_castep_bin):
    """A stored+reloaded ForceConstantsData yields equivalent force constants."""
    original = ForceConstants.from_castep(quartz_castep_bin)

    node = ForceConstantsData(original)
    node.store()  # persist to the temporary profile
    reloaded = node.get_force_constants()

    assert reloaded.crystal.n_atoms == original.crystal.n_atoms
    assert_equivalent_force_constants(reloaded, original)


def test_force_constants_from_castep_classmethod(aiida_profile, quartz_castep_bin):
    """The ``from_castep`` constructor produces a usable node."""
    node = ForceConstantsData.from_castep(quartz_castep_bin)
    assert node.get_force_constants().crystal.n_atoms == 9  # quartz: 3 Si + 6 O


def test_force_constants_type_validation(aiida_profile):
    """Passing a non-ForceConstants object raises TypeError."""
    with pytest.raises(TypeError):
        ForceConstantsData("not a force constants object")


def test_crystal_roundtrip_and_structure_bridge(aiida_profile, quartz_castep_bin):
    """EuphonicCrystalData round-trips and bridges to/from StructureData."""
    crystal = ForceConstants.from_castep(quartz_castep_bin).crystal

    node = EuphonicCrystalData(crystal)
    node.store()
    assert node.get_crystal().n_atoms == crystal.n_atoms

    structure = node.to_structure()
    assert isinstance(structure, StructureData)
    assert len(structure.sites) == crystal.n_atoms
    assert structure.pbc == (True, True, True)

    # StructureData -> EuphonicCrystalData -> spglib cell round-trip preserves atoms
    rebuilt = EuphonicCrystalData.from_structure(structure)
    lattice, _positions, numbers = rebuilt.to_spglib_cell()
    assert len(numbers) == crystal.n_atoms
    np.testing.assert_allclose(
        np.asarray(lattice),
        crystal.cell_vectors.to("angstrom").magnitude,
        rtol=1e-6,
    )


def test_force_constants_from_phonopy(aiida_profile, phonopy_dir):
    """ForceConstantsData.from_phonopy reads a Phonopy example (NaCl)."""
    node = ForceConstantsData.from_phonopy(
        path=str(phonopy_dir),
        summary_name="phonopy.yaml",
        fc_name="FORCE_CONSTANTS",
        born_name="BORN",
    )
    assert node.get_force_constants().crystal.n_atoms == 8  # NaCl: 4 Na + 4 Cl


def test_qpoint_phonon_modes_roundtrip(aiida_profile, quartz_castep_bin):
    """A stored+reloaded QpointPhononModesData reproduces frequencies."""
    force_constants = ForceConstants.from_castep(quartz_castep_bin)
    qpts = np.array([[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]])
    modes = force_constants.calculate_qpoint_phonon_modes(qpts)

    node = QpointPhononModesData(modes)
    node.store()
    reloaded = node.get_modes()

    np.testing.assert_allclose(
        reloaded.frequencies.magnitude, modes.frequencies.magnitude
    )
