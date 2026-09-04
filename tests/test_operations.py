"""Tests for the atomic Euphonic operations and their PythonJob wrappers."""

from __future__ import annotations

import logging
import subprocess

import numpy as np
import pytest

# Imported directly so the equivalence test can call the underlying library the
# same way `calculate_tosca_spectrum` does (see the project's testing convention:
# prefer equivalence against a direct public-API call over reference values).
from abinslib.almost_isotropic_incoherent import (
    calculate_almost_isotropic_incoherent_spectra,
    mantid_like_combination_spectra,
)
from abinslib.displacements import Displacements
from abinslib.util import apply_weights
from aiida.engine import run_get_node
from aiida.orm import XyData
from aiida_pythonjob import PythonJob
from euphonic import ForceConstants, QpointPhononModes, Quantity, Spectrum1D, ureg

from aiida_pythonjob_ins.data import ForceConstantsData, QpointPhononModesData
from aiida_pythonjob_ins.operations import (
    broaden_tosca_spectrum,
    calculate_dispersion,
    calculate_dos,
    calculate_scattering_q2,
    calculate_thermal_displacements,
    calculate_tosca_spectrum,
    default_energy_bins,
    read_force_constants_from_castep,
    tosca_energy_bins,
)
from aiida_pythonjob_ins.pythonjobs import (
    prepare_dispersion_inputs,
    prepare_dos_inputs,
    prepare_read_phonopy_inputs,
    prepare_tosca_spectrum_inputs,
)

OPS_LOGGER = "aiida_pythonjob_ins.operations"


def test_operations_emit_logs(quartz_castep_bin, caplog):
    """The atomic operations emit informative INFO log records.

    Verifies the library's logging is wired correctly. Library code only emits
    (never configures) logging, so the test raises the level via ``caplog``.
    ``calculate_dispersion`` chains the band-path and interpolation helpers, so it
    exercises both of their log messages.
    """
    with caplog.at_level(logging.INFO, logger=OPS_LOGGER):
        force_constants = read_force_constants_from_castep(quartz_castep_bin)
        calculate_dispersion(force_constants, q_spacing=0.3)

    messages = [rec.getMessage() for rec in caplog.records if rec.name == OPS_LOGGER]
    assert any("Reading force constants" in msg for msg in messages)
    assert any("Generated band path" in msg for msg in messages)
    assert any("Computing phonon modes" in msg for msg in messages)


def test_calculate_dispersion_pure_function(quartz_castep_bin):
    """The plain function returns modes on a non-trivial band path."""
    force_constants = ForceConstants.from_castep(quartz_castep_bin)
    modes = calculate_dispersion(force_constants, q_spacing=0.1)

    n_branches = force_constants.crystal.n_atoms * 3
    assert modes.frequencies.shape[1] == n_branches
    assert modes.frequencies.shape[0] > 1  # multiple q-points along the path


@pytest.mark.venv_code
@pytest.mark.parametrize("code", ["python_code", "remote_python_code"], indirect=True)
def test_dispersion_pythonjob_matches_direct_call(code, quartz_castep_bin):
    """Running via PythonJob reproduces a direct public-API computation.

    This is an *equivalence* test: rather than hard-coding reference frequencies,
    we compare the AiiDA-wrapped result against calling Euphonic directly.

    Parametrized to run with both the local interpreter (python_code) and the
    AiiDA-free child interpreter (remote_python_code) to verify that PythonJob
    functions work in a minimal environment.
    """
    q_spacing = 0.1
    force_constants = ForceConstants.from_castep(quartz_castep_bin)
    expected = calculate_dispersion(force_constants, q_spacing=q_spacing)

    fc_node = ForceConstantsData(force_constants)
    inputs = prepare_dispersion_inputs(fc_node, q_spacing=q_spacing, code=code)
    results, node = run_get_node(PythonJob, **inputs)

    assert node.is_finished_ok, node.exit_status
    modes_node = results["result"]
    assert isinstance(modes_node, QpointPhononModesData)

    # Tolerances allow for eigensolver numerical noise: the two computations run
    # in different processes (in-process vs the PythonJob subprocess), so BLAS/
    # LAPACK threading can perturb near-degenerate acoustic modes at ~1e-2 meV.
    np.testing.assert_allclose(
        modes_node.get_modes().frequencies.magnitude,
        expected.frequencies.magnitude,
        rtol=1e-3,
        atol=0.05,  # meV
    )


@pytest.mark.venv_code
def test_child_environment_lacks_aiida(venv_child_environment):
    """Verify that the child environment cannot import AiiDA.

    This test exists to make Decision 5's precondition visible in the test
    report, rather than buried in fixture setup. It verifies that the
    venv_child_environment fixture correctly removed AiiDA packages.
    """
    # Test that aiida cannot be imported
    result = subprocess.run(
        [str(venv_child_environment), "-c", "import aiida"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0, "AiiDA should not be importable in child environment"

    # Test that aiida_pythonjob cannot be imported
    result = subprocess.run(
        [str(venv_child_environment), "-c", "import aiida_pythonjob"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0, (
        "aiida_pythonjob should not be importable in child environment"
    )


def test_calculate_dos_pure_function(quartz_castep_bin):
    """The plain DOS function returns a Spectrum1D with matching x/y lengths."""
    force_constants = ForceConstants.from_castep(quartz_castep_bin)
    dos = calculate_dos(force_constants, q_spacing=0.5, energy_spacing=2.0)

    assert isinstance(dos, Spectrum1D)
    # Histogram-like: x holds bin edges, get_bin_centres() matches y.
    assert len(dos.get_bin_centres()) == len(dos.y_data)
    assert (dos.y_data.magnitude >= 0).all()


def test_default_energy_bins_stable():
    """Stable frequencies clamp cleanly at 0.0 with 5% upper padding."""
    freqs = np.array([0.0, 5.0, 20.0]) * ureg.meV
    bins = default_energy_bins(freqs, 1.0 * ureg.meV)

    # Span = 20.0 meV, pad = 1.0 meV. Upper = 21.0 meV, lower = 0.0 meV.
    assert bins.units == ureg.meV
    assert bins[0] == 0.0 * ureg.meV
    assert bins[-1] == 21.0 * ureg.meV
    np.testing.assert_allclose(bins.magnitude, np.arange(0.0, 22.0, 1.0))


def test_default_energy_bins_negative_modes():
    """Negative/imaginary frequencies receive 5% padding below the minimum."""
    freqs = np.array([-10.0, 5.0, 30.0]) * ureg.meV
    bins = default_energy_bins(freqs, 1.0 * ureg.meV)

    # Span = 40.0 meV, pad = 2.0 meV. Upper = 32.0 meV, lower = -12.0 meV.
    assert bins.units == ureg.meV
    assert bins[0] == -12.0 * ureg.meV
    assert bins[-1] == 32.0 * ureg.meV
    np.testing.assert_allclose(bins.magnitude, np.arange(-12.0, 33.0, 1.0))


def test_default_energy_bins_cross_unit():
    """Quantity conversions work across spectroscopy contexts (e.g. THz to meV)."""
    freqs = np.array([0.0, 2.0, 5.0]) * ureg.THz
    bins = default_energy_bins(freqs, 1.0 * ureg.meV)

    # 5.0 THz = 20.678... meV. Span = 20.678... meV, pad = 1.0339... meV.
    # Upper = 21.712... meV -> ceil is 22.0 meV. Lower = 0.0 meV.
    assert bins.units == ureg.meV
    assert bins[0] == 0.0 * ureg.meV
    assert bins[-1] == 22.0 * ureg.meV
    np.testing.assert_allclose(bins.magnitude, np.arange(0.0, 23.0, 1.0))


def test_calculate_dos_preserves_negative_frequencies(quartz_castep_bin):
    """DOS on a dataset with negative frequencies spans below zero."""
    force_constants = ForceConstants.from_castep(quartz_castep_bin)
    dos = calculate_dos(force_constants, q_spacing=0.5, energy_spacing=1.0)

    # Quartz CASTEP force constants have small negative acoustic modes at zone centre,
    # so the padded energy axis extends into negative frequencies.
    assert dos.x_data[0] < 0.0 * ureg.meV


def test_calculate_dos_sum_rule(quartz_castep_bin):
    """Integrating DOS across the padded axis recovers 3 modes per formula unit."""
    force_constants = ForceConstants.from_castep(quartz_castep_bin)
    energy_spacing = 0.5

    # 1. Fixed binning (adaptive=False): all modes binned, integral is exact
    dos_fixed = calculate_dos(
        force_constants,
        q_spacing=0.2,
        energy_spacing=energy_spacing,
        adaptive=False,
    )
    integral_fixed = np.sum(dos_fixed.y_data.to("1/meV").magnitude * energy_spacing)
    np.testing.assert_allclose(integral_fixed, 3.0, rtol=1e-10)

    # 2. Adaptive broadening (adaptive=True): continuous Gaussian wings near edges
    dos_adaptive = calculate_dos(
        force_constants,
        q_spacing=0.2,
        energy_spacing=energy_spacing,
        adaptive=True,
    )
    integral_adaptive = np.sum(
        dos_adaptive.y_data.to("1/meV").magnitude * energy_spacing
    )
    np.testing.assert_allclose(integral_adaptive, 3.0, rtol=0.01)


def test_dos_pythonjob_returns_xydata(python_code, quartz_castep_bin):
    """Running the DOS op via PythonJob yields a native XyData."""
    force_constants = ForceConstants.from_castep(quartz_castep_bin)
    fc_node = ForceConstantsData(force_constants)
    inputs = prepare_dos_inputs(
        fc_node, q_spacing=0.5, energy_spacing=2.0, code=python_code
    )
    results, node = run_get_node(PythonJob, **inputs)

    assert node.is_finished_ok, node.exit_status
    dos_node = results["result"]
    assert isinstance(dos_node, XyData)
    _, energy, _ = dos_node.get_x()
    ((_, dos_values, _),) = dos_node.get_y()
    assert len(energy) == len(dos_values)


def test_read_phonopy_pythonjob(python_code, phonopy_files):
    """Reading Phonopy input via PythonJob yields a ForceConstantsData."""
    inputs = prepare_read_phonopy_inputs(
        summary=phonopy_files["summary"],
        force_constants=phonopy_files["force_constants"],
        born=phonopy_files["born"],
        code=python_code,
    )
    results, node = run_get_node(PythonJob, **inputs)

    assert node.is_finished_ok, node.exit_status
    fc_node = results["result"]
    assert isinstance(fc_node, ForceConstantsData)
    assert fc_node.get_force_constants().crystal.n_atoms == 8


# --- TOSCA scattering-intensity operations -------------------------------------


@pytest.fixture
def ethanol_modes(ethanol_modes_json) -> QpointPhononModes:
    """The bundled ethanol phonon modes, loaded directly with Euphonic."""
    return QpointPhononModes.from_json_file(ethanol_modes_json)


def test_calculate_thermal_displacements_changes_with_temperature(ethanol_modes):
    """Thermal displacements differ between two sample temperatures."""
    _, low_t = calculate_thermal_displacements(ethanol_modes, 10.0)
    _, high_t = calculate_thermal_displacements(ethanol_modes, 300.0)
    assert not np.allclose(low_t.magnitude, high_t.magnitude)


def test_calculate_scattering_q2_differs_by_angle(ethanol_modes):
    """Different scattering angles give different momentum transfer."""
    q2_backward = calculate_scattering_q2(ethanol_modes.frequencies, 135.0, 32.0)
    q2_forward = calculate_scattering_q2(ethanol_modes.frequencies, 45.0, 32.0)
    assert not np.allclose(q2_backward.magnitude, q2_forward.magnitude)


def test_tosca_energy_bins_reach_the_scaled_fundamental_range(ethanol_modes):
    """With a high instrument maximum, the axis is sized from the data."""
    spacing = Quantity(10.0, "1/cm")
    high_max = Quantity(20000.0, "1/cm")  # comfortably above any combination mode
    bins = tosca_energy_bins(ethanol_modes.frequencies, spacing, high_max)

    fundamental_max = ethanol_modes.frequencies.to("1/cm").magnitude.max()
    # Combination modes reach ~2x the highest fundamental; the axis must too.
    assert bins[-1].to("1/cm").magnitude >= 2 * fundamental_max
    assert bins[-1] < high_max


def test_tosca_energy_bins_clipped_by_instrument_maximum(ethanol_modes):
    """A low instrument maximum overrides the data-sized range."""
    spacing = Quantity(10.0, "1/cm")
    low_max = Quantity(500.0, "1/cm")
    bins = tosca_energy_bins(ethanol_modes.frequencies, spacing, low_max)
    assert bins[-1] <= low_max


def test_tosca_energy_bins_are_never_negative(ethanol_modes):
    """The axis starts at zero even though frequencies dip slightly below it.

    Unlike a DOS, an energy transfer below zero is kinematically inaccessible
    for TOSCA (see the docstring of `tosca_energy_bins`); this also guards
    against `calculate_scattering_q2` receiving values that make it take the
    square root of a negative number.
    """
    assert ethanol_modes.frequencies.to("1/cm").magnitude.min() < 0
    bins = tosca_energy_bins(
        ethanol_modes.frequencies, Quantity(10.0, "1/cm"), Quantity(4000.0, "1/cm")
    )
    assert bins.magnitude.min() == 0.0


def test_tosca_energy_bins_honour_the_spacing(ethanol_modes):
    """Bin edges are spaced by the requested energy_spacing."""
    spacing = Quantity(25.0, "1/cm")
    bins = tosca_energy_bins(
        ethanol_modes.frequencies, spacing, Quantity(4000.0, "1/cm")
    )
    np.testing.assert_allclose(np.diff(bins.magnitude), 25.0)


def test_calculate_tosca_spectrum_matches_direct_abinslib_call(ethanol_modes):
    """calculate_tosca_spectrum reproduces a direct abinslib + resins call.

    Equivalence test (per this project's convention): rather than hard-coding
    reference intensities, the same sequence is performed directly against the
    underlying libraries' public interfaces, for one detector bank.
    """
    temperature = 25.0
    energy_spacing = 20.0
    energy_max = 2000.0
    angle = 135.0
    final_energy = 32.0

    actual = calculate_tosca_spectrum(
        ethanol_modes,
        temperature=temperature,
        energy_spacing=energy_spacing,
        energy_max=energy_max,
        detector_angles=[angle],
        final_energy=final_energy,
    )

    mode_displacements = Displacements.from_modes(
        ethanol_modes, Quantity(temperature, "K")
    )
    atomic_displacements = mode_displacements.to_atomic_displacements()
    bins = tosca_energy_bins(
        ethanol_modes.frequencies,
        Quantity(energy_spacing, "1/cm"),
        Quantity(energy_max, "1/cm"),
    )
    bin_centres = (bins[1:] + bins[:-1]) / 2
    fundamental_q2 = calculate_scattering_q2(
        ethanol_modes.frequencies, angle, final_energy
    )
    combination_q2 = calculate_scattering_q2(bin_centres, angle, final_energy)

    fundamentals = calculate_almost_isotropic_incoherent_spectra(
        modes=ethanol_modes,
        mode_displacements=mode_displacements,
        atomic_displacements=atomic_displacements,
        nominal_q2=fundamental_q2,
        bins=bins,
    )
    combinations = mantid_like_combination_spectra(
        ethanol_modes, mode_displacements, atomic_displacements, combination_q2, bins
    )
    # Apply cross-section weights then group.
    raw_bank = fundamentals + combinations
    weighted_bank = apply_weights(raw_bank, key="scattering_cross_section")
    expected = weighted_bank.group_by("atom_index", "quantum_order")

    np.testing.assert_allclose(actual.y_data.magnitude, expected.y_data.magnitude)


def test_calculate_tosca_spectrum_default_banks_are_both_present(ethanol_modes):
    """Without an explicit choice of angles, both TOSCA banks are evaluated."""
    spectrum = calculate_tosca_spectrum(ethanol_modes, energy_spacing=50.0)
    angles = {line["detector_angle"] for line in spectrum.metadata["line_data"]}
    assert angles == {135.0, 45.0}


def test_calculate_tosca_spectrum_lines_carry_order_and_symbol(ethanol_modes):
    """Every line is labelled with its quantum order, atom symbol and mass."""
    spectrum = calculate_tosca_spectrum(
        ethanol_modes, detector_angles=[135.0], energy_spacing=50.0
    )
    orders = {line["quantum_order"] for line in spectrum.metadata["line_data"]}
    symbols = {line["atom_symbol"] for line in spectrum.metadata["line_data"]}
    # Mass metadata is present on each line
    masses = {line["mass"] for line in spectrum.metadata["line_data"]}
    assert orders == {1, 2}
    assert symbols == {"C", "O", "H"}
    assert len(masses) > 0  # mass metadata is present


def test_calculate_tosca_spectrum_has_barn_units(ethanol_modes):
    """Cross-section weighted intensities have units of barn * cm."""
    spectrum = calculate_tosca_spectrum(ethanol_modes, energy_spacing=50.0)
    # apply_weights produces physical cross-section-weighted units
    assert "barn" in str(spectrum.y_data.units)


def test_calculate_tosca_spectrum_collapses_only_the_qpoint_dimension(ethanol_modes):
    """q-point duplicates are merged; every other distinction is preserved.

    abinslib's combination-mode routine returns lines resolved per q-point,
    which would otherwise multiply the committed y arrays by the q-point count
    and leak a `qpt` key into every plot label.
    """
    spectrum = calculate_tosca_spectrum(ethanol_modes, energy_spacing=20.0)
    line_data = spectrum.metadata["line_data"]

    n_atoms = ethanol_modes.crystal.n_atoms
    assert len(spectrum) == n_atoms * 2 * 2  # atoms x quantum orders x banks

    # The q-point dimension is gone...
    assert all("qpt" not in line for line in line_data)
    # ...and nothing else was merged with it: each combination is still distinct.
    triples = [
        (line["atom_index"], line["quantum_order"], line["detector_angle"])
        for line in line_data
    ]
    assert len(set(triples)) == len(triples)
    assert all("atom_symbol" in line for line in line_data)


def test_calculate_tosca_spectrum_is_physically_plausible(ethanol_modes):
    """The summed spectrum is finite, non-negative and not uniformly zero."""
    spectrum = calculate_tosca_spectrum(ethanol_modes, energy_spacing=20.0)
    total = spectrum.sum().y_data.magnitude
    assert np.isfinite(total).all()
    assert (total >= 0).all()
    assert total.max() > 0


def test_broaden_tosca_spectrum_changes_the_result(ethanol_modes):
    """Broadening is applied: the result differs and stays finite/non-negative."""
    spectrum = calculate_tosca_spectrum(ethanol_modes, energy_spacing=20.0).sum()
    broadened = broaden_tosca_spectrum(spectrum)
    assert np.isfinite(broadened.y_data.magnitude).all()
    assert (broadened.y_data.magnitude >= 0).all()
    assert not np.allclose(broadened.y_data.magnitude, spectrum.y_data.magnitude)


def test_broadening_commutes_with_summation(ethanol_modes):
    """Broadening then summing agrees with summing then broadening.

    The resolution operator is linear, so the two orders must agree to
    numerical precision (tosca-spectra: "Broadening commutes with summation").
    """
    spectrum = calculate_tosca_spectrum(
        ethanol_modes, detector_angles=[135.0], energy_spacing=20.0
    )

    broadened_then_summed = broaden_tosca_spectrum(spectrum).sum()
    summed_then_broadened = broaden_tosca_spectrum(spectrum.sum())

    np.testing.assert_allclose(
        broadened_then_summed.y_data.magnitude,
        summed_then_broadened.y_data.magnitude,
        rtol=1e-10,
    )


def test_tosca_pythonjob_returns_multiline_xydata(python_code, ethanol_modes_json):
    """Running the TOSCA op via PythonJob yields a multi-line, labelled XyData."""
    modes_node = QpointPhononModesData.from_json_file(ethanol_modes_json)
    inputs = prepare_tosca_spectrum_inputs(
        modes_node,
        detector_angles=[135.0, 45.0],
        energy_spacing=50.0,
        code=python_code,
    )
    results, node = run_get_node(PythonJob, **inputs)

    assert node.is_finished_ok, node.exit_status
    xy = results["result"]
    assert isinstance(xy, XyData)

    _, energy, _ = xy.get_x()
    y_entries = xy.get_y()
    modes = QpointPhononModes.from_json_file(ethanol_modes_json)
    # One line per (atom, quantum order, detector bank).
    assert len(y_entries) == modes.crystal.n_atoms * 2 * 2
    for name, values, _ in y_entries:
        assert name  # every line is labelled
        assert values.shape == energy.shape
        assert np.isfinite(values).all()
        assert (values >= 0).all()
