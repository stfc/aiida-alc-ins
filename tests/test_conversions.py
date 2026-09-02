"""Tests for mapping Euphonic results onto native AiiDA KpointsData/BandsData."""

from __future__ import annotations

import matplotlib as mpl
import numpy as np
import pytest
from aiida.engine import run_get_node
from aiida.orm import BandsData, Float, KpointsData, StructureData, XyData
from aiida_pythonjob import PythonJob
from euphonic import ForceConstants, QpointPhononModes

from aiida_pythonjob_ins.conversions import (
    qpoints_to_kpoints_data,
    spectrum1d_to_xydata,
    spectrum_collection_labels,
    spectrum_collection_to_xydata,
    xydata_to_spectrum_collection,
)
from aiida_pythonjob_ins.data import ForceConstantsData, QpointPhononModesData
from aiida_pythonjob_ins.operations import (
    calculate_dispersion,
    calculate_dos,
    calculate_tosca_spectrum,
    interpolate_phonon_modes,
)
from aiida_pythonjob_ins.pythonjobs import prepare_interpolation_inputs
from aiida_pythonjob_ins.workflows.dispersion import (
    extract_structure,
    generate_band_path,
)


def test_kpoints_roundtrip(aiida_profile):
    """qpoints -> KpointsData -> qpoints preserves positions and labels."""
    qpts = np.array([[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [0.5, 0.5, 0.0]])
    cell = np.eye(3) * 4.0
    labels = [(0, "\u0393"), (2, "M")]

    kpoints = qpoints_to_kpoints_data(qpts, cell, labels=labels)
    np.testing.assert_allclose(kpoints.get_kpoints(), qpts)
    assert kpoints.labels == labels


def test_modes_data_to_native_types(aiida_profile, quartz_castep_bin):
    """QpointPhononModesData exposes KpointsData and BandsData views."""
    force_constants = ForceConstants.from_castep(quartz_castep_bin)
    qpts = np.array([[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]])
    modes = force_constants.calculate_qpoint_phonon_modes(qpts)
    node = QpointPhononModesData(modes)

    kpoints = node.to_kpoints()
    assert isinstance(kpoints, KpointsData)
    np.testing.assert_allclose(kpoints.get_kpoints(), qpts)

    bands = node.to_bands()
    assert isinstance(bands, BandsData)
    n_branches = force_constants.crystal.n_atoms * 3
    assert bands.get_bands().shape == (len(qpts), n_branches)


def test_to_structure(aiida_profile, quartz_castep_bin):
    """ForceConstantsData exposes its crystal as a native StructureData."""
    node = ForceConstantsData.from_castep(quartz_castep_bin)
    structure = node.to_structure()
    assert isinstance(structure, StructureData)
    # quartz: 3 Si + 6 O
    assert len(structure.sites) == 9
    assert {kind.symbol for kind in structure.kinds} == {"Si", "O"}


def test_extract_structure_is_generic(aiida_profile, quartz_castep_bin):
    """extract_structure works on any node with to_structure() (here: modes)."""
    force_constants = ForceConstants.from_castep(quartz_castep_bin)
    modes = force_constants.calculate_qpoint_phonon_modes(np.array([[0.0, 0.0, 0.0]]))
    modes_node = QpointPhononModesData(modes).store()

    structure = extract_structure(modes_node)  # inherited to_structure()
    assert isinstance(structure, StructureData)
    assert len(structure.sites) == force_constants.crystal.n_atoms


def test_modes_to_bands_without_kpoints_uses_euphonic_labels(
    aiida_profile, quartz_castep_bin
):
    """Without a KpointsData, labels fall back to Euphonic's automatic ticks."""
    force_constants = ForceConstants.from_castep(quartz_castep_bin)
    modes = calculate_dispersion(force_constants, q_spacing=0.3)
    bands = QpointPhononModesData(modes).to_bands()  # no kpoints
    assert bands.labels  # euphonic derived at least Gamma


def test_modes_to_bands_validates_mismatched_kpoints(aiida_profile, quartz_castep_bin):
    """A KpointsData whose q-points disagree with the modes is rejected."""
    force_constants = ForceConstants.from_castep(quartz_castep_bin)
    modes = force_constants.calculate_qpoint_phonon_modes(
        np.array([[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]])
    )
    node = QpointPhononModesData(modes)
    wrong = qpoints_to_kpoints_data(
        np.array([[0.1, 0.1, 0.1], [0.2, 0.2, 0.2]]),
        force_constants.crystal.cell_vectors.to("angstrom").magnitude,
    )
    with pytest.raises(ValueError, match="do not match"):
        node.to_bands(wrong)


def test_spectrum1d_to_xydata(aiida_profile, quartz_castep_bin):
    """A Euphonic DOS Spectrum1D maps to an XyData with matching x/y lengths."""
    force_constants = ForceConstants.from_castep(quartz_castep_bin)
    dos = calculate_dos(force_constants, q_spacing=0.5, energy_spacing=2.0)

    xy = spectrum1d_to_xydata(dos)
    assert isinstance(xy, XyData)
    _, energy, _ = xy.get_x()
    ((_, values, _),) = xy.get_y()
    np.testing.assert_allclose(energy, dos.get_bin_centres().magnitude)
    np.testing.assert_allclose(values, dos.y_data.magnitude)


def test_bandsdata_matplotlib_export(aiida_profile, quartz_castep_bin, tmp_path):
    """BandsData renders a band-structure image via matplotlib (no AiiDALab)."""
    mpl.use("Agg")  # headless

    force_constants = ForceConstants.from_castep(quartz_castep_bin)
    modes = calculate_dispersion(force_constants, q_spacing=0.3)
    bands = QpointPhononModesData(modes).to_bands()
    bands.store()

    out = tmp_path / "bands.png"
    bands.export(str(out), fileformat="mpl_png")
    assert out.exists()
    assert out.stat().st_size > 0


def test_interpolation_from_kpoints_matches_direct(python_code, quartz_castep_bin):
    """The KpointsData-driven interpolation PythonJob matches a direct call.

    Demonstrates KpointsData as the q-point specification input for the
    ForceConstants -> QpointPhononModes step.
    """
    force_constants = ForceConstants.from_castep(quartz_castep_bin)
    fc_node = ForceConstantsData(force_constants).store()

    # Build the path as a KpointsData via the parent-side calcfunctions
    # (force constants -> structure -> seekpath path).
    structure = extract_structure(fc_node)
    kpoints = generate_band_path(structure, Float(0.2))
    assert isinstance(kpoints, KpointsData)

    expected = interpolate_phonon_modes(force_constants, kpoints.get_kpoints())

    results, node = run_get_node(
        PythonJob,
        **prepare_interpolation_inputs(fc_node, kpoints, code=python_code),
    )
    assert node.is_finished_ok, node.exit_status
    modes_node = results["result"]
    assert isinstance(modes_node, QpointPhononModesData)

    # Tolerances absorb eigensolver noise on near-degenerate acoustic modes.
    np.testing.assert_allclose(
        modes_node.get_modes().frequencies.magnitude,
        expected.frequencies.magnitude,
        rtol=1e-3,
        atol=0.05,  # meV
    )


def _ethanol_tosca_spectrum(ethanol_modes_json):
    """A small TOSCA collection (one bank, coarse bins) for conversion tests."""
    modes = QpointPhononModes.from_json_file(ethanol_modes_json)
    return calculate_tosca_spectrum(modes, detector_angles=[135.0], energy_spacing=20.0)


def test_spectrum_collection_to_xydata(aiida_profile, ethanol_modes_json):
    """A Spectrum1DCollection becomes one XyData with one y array per line."""
    spectrum = _ethanol_tosca_spectrum(ethanol_modes_json)

    xy = spectrum_collection_to_xydata(spectrum)
    assert isinstance(xy, XyData)

    _, x_values, _ = xy.get_x()
    y_entries = xy.get_y()
    np.testing.assert_allclose(x_values, spectrum.get_bin_centres().magnitude)
    assert len(y_entries) == len(spectrum)
    for _, y_values, _ in y_entries:
        assert y_values.shape == x_values.shape


def test_spectrum_collection_roundtrip_preserves_metadata(
    aiida_profile, ethanol_modes_json
):
    """Collection -> XyData -> collection preserves values and metadata."""
    spectrum = _ethanol_tosca_spectrum(ethanol_modes_json)

    xy = spectrum_collection_to_xydata(spectrum)
    xy.store()  # attributes become immutable once stored, as provenance requires
    recovered = xydata_to_spectrum_collection(xy)

    assert len(recovered) == len(spectrum)
    np.testing.assert_allclose(
        recovered.get_bin_centres().magnitude, spectrum.get_bin_centres().magnitude
    )
    np.testing.assert_allclose(recovered.y_data.magnitude, spectrum.y_data.magnitude)
    assert recovered.metadata == spectrum.metadata


def test_recovered_collection_groups_like_the_original(
    aiida_profile, ethanol_modes_json
):
    """Grouping a recovered collection matches grouping the original."""
    spectrum = _ethanol_tosca_spectrum(ethanol_modes_json)
    recovered = xydata_to_spectrum_collection(spectrum_collection_to_xydata(spectrum))

    for key in ("atom_symbol", "quantum_order"):
        original_group = spectrum.group_by(key)
        recovered_group = recovered.group_by(key)
        np.testing.assert_allclose(
            recovered_group.y_data.magnitude, original_group.y_data.magnitude
        )


def test_spectrum_collection_labels_are_readable(aiida_profile, ethanol_modes_json):
    """Lines that differ in metadata get distinct, readable labels."""
    spectrum = _ethanol_tosca_spectrum(ethanol_modes_json)

    by_symbol = spectrum.group_by("atom_symbol")
    labels = spectrum_collection_labels(by_symbol)
    # Mass metadata is included in labels when it varies, supporting
    # isotopic substitution systems where mass distinguishes isotopes
    assert set(labels) == {"C (12.0107)", "H (1.00794)", "O (15.9994)"}

    by_order = spectrum.group_by("quantum_order")
    order_labels = spectrum_collection_labels(by_order)
    # The 'method' metadata describes the scattering approach and varies
    # between fundamentals (order 1) and combinations (order 2)
    assert order_labels == [
        "Order 1, almost-isotropic incoherent",
        "Order 2, almost-isotropic incoherent approximation",
    ]

    # Grouped down to one line: nothing left varies, so it reads as a total
    # rather than repeating metadata that is now common to everything.
    total = spectrum.group_by()
    assert spectrum_collection_labels(total) == ["Total"]
