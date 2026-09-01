"""Atomic Euphonic operations, written as plain Python functions.

These functions use only the **public** Euphonic API and know nothing about
AiiDA, so they can be unit-tested directly and reused elsewhere. Crucially, this
module's import chain is AiiDA-free (the package ``__init__`` is empty), so
by-reference cloudpickling can target a lean remote environment (euphonic +
seekpath + numpy, no aiida). They are turned into AiiDA PythonJobs by the
helpers in :mod:`aiida_pythonjob_ins.pythonjobs`.

The dispersion workflow is built from composable pieces, mirroring
``euphonic.cli.dispersion`` (https://euphonic.readthedocs.io/en/stable/cli.html)
without relying on Euphonic's private ``_bands_from_force_constants`` helper:

1. :func:`band_path_qpoints` -- build a high-symmetry q-point path (seekpath).
2. :func:`interpolate_phonon_modes` -- Fourier-interpolate modes at those points.

``calculate_dispersion`` is a convenience that chains the two. The band path is
turned into a native ``KpointsData`` by a parent-side ``calcfunction`` (see
:func:`aiida_pythonjob_ins.workflows.dispersion.generate_band_path`), so these
functions stay AiiDA-free and unit-testable.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import numpy as np
import seekpath

if TYPE_CHECKING:
    import pint

# Imported at module level (not under TYPE_CHECKING) because aiida-pythonjob
# resolves the function's type hints at runtime via ``typing.get_type_hints``.
from abinslib.almost_isotropic_incoherent import (
    calculate_almost_isotropic_incoherent_spectra,
    mantid_like_combination_spectra,
)
from abinslib.displacements import Displacements
from abinslib.util import apply_weights, calculate_indirect_q2
from euphonic import (
    ForceConstants,
    QpointPhononModes,
    Quantity,
    Spectrum1D,
    Spectrum1DCollection,
    ureg,
)
from euphonic.util import mode_gradients_to_widths, mp_grid
from resins import Instrument

# Library code only *emits* logs; it never configures handlers or levels -- the
# host application (or AiiDA) decides how these are surfaced. When these functions
# run inside a PythonJob, their stdout/stderr are captured into the job's retrieved
# files, so configured logging is preserved in provenance.
LOGGER = logging.getLogger(__name__)


class QpointPath(NamedTuple):
    """A high-symmetry q-point path: positions + labels + cell (no energies).

    A well-defined return type for :func:`band_path_qpoints`. It is a plain
    ``NamedTuple`` used purely on the Python side; the parent-side
    ``generate_band_path`` calcfunction turns it into a native ``KpointsData``.

    (Note: aiida-pythonjob would treat a ``NamedTuple`` *return annotation* as a
    structured multi-output spec, splitting it into one output port per field. That
    does not apply here because ``band_path_qpoints`` is not used as a PythonJob
    ``function`` -- if it were, the split into qpoints/labels/cell could even be
    desirable.)
    """

    qpoints: np.ndarray
    labels: list[tuple[int, str]]
    cell: np.ndarray


def read_force_constants_from_castep(filename: str | Path) -> ForceConstants:
    """Read a CASTEP ``.castep_bin``/``.check`` file into ``ForceConstants``.

    A thin wrapper over ``ForceConstants.from_castep``. It exists because a
    PythonJob's ``function`` must be a plain module-level function: a bound
    classmethod (``ForceConstants.from_castep``) is a ``method``, not a
    ``FunctionType``, so aiida-pythonjob's ``build_function_data`` rejects it. The
    wrapper is also where we attach logging.

    ``filename`` is resolved relative to the working directory. When run as a
    PythonJob the CASTEP file is staged there via ``upload_files`` (see
    :func:`aiida_pythonjob_ins.pythonjobs.prepare_read_force_constants_inputs`).
    """
    LOGGER.info("Reading force constants from CASTEP file: %s", filename)
    return ForceConstants.from_castep(filename)


def read_force_constants_from_phonopy(
    summary_name: str = "phonopy.yaml",
    fc_name: str = "FORCE_CONSTANTS",
    born_name: str | None = None,
) -> ForceConstants:
    """Read force constants from Phonopy output into ``ForceConstants``.

    Thin wrapper over ``ForceConstants.from_phonopy`` (requires euphonic's
    ``phonopy-reader`` extra, which this package installs by default). All names
    are resolved in the working directory; when run as a PythonJob the files are
    staged there via ``upload_files`` (see
    :func:`aiida_pythonjob_ins.pythonjobs.prepare_read_phonopy_inputs`).

    ``born_name`` is optional (Born charges for LO-TO splitting); pass ``None`` to
    skip it.
    """
    LOGGER.info(
        "Reading force constants from Phonopy: summary=%s fc=%s born=%s",
        summary_name,
        fc_name,
        born_name,
    )
    return ForceConstants.from_phonopy(
        path=".", summary_name=summary_name, fc_name=fc_name, born_name=born_name
    )


def band_path_qpoints(
    cell: tuple[np.ndarray, np.ndarray, np.ndarray],
    q_spacing: float = 0.025,
    *,
    insert_gamma: bool = True,
) -> QpointPath:
    """Return a :class:`QpointPath` (q-points + labels + cell) for a band path.

    ``cell`` is a spglib-style ``(lattice, scaled_positions, numbers)`` tuple --
    e.g. from ``euphonic.Crystal.to_spglib_cell()`` or an ASE ``Atoms``. Only the
    structure is needed; force constants are not. Pure/AiiDA-free: the parent-side
    ``generate_band_path`` calcfunction wraps this into a native ``KpointsData``.
    """
    # Work in the *original* cell so the returned q-points are valid inputs to
    # ``calculate_qpoint_phonon_modes`` (which uses the same cell's reciprocal basis).
    bandpath = seekpath.get_explicit_k_path_orig_cell(
        cell, reference_distance=q_spacing
    )

    labels = list(bandpath["explicit_kpoints_labels"])
    qpts = np.asarray(bandpath["explicit_kpoints_rel"])

    if insert_gamma:
        # Duplicate Gamma points so LO-TO splitting can be represented (matches
        # Euphonic's default behaviour).
        gamma_indices = [i for i in range(1, len(labels) - 1) if labels[i] == "GAMMA"]
        for index in reversed(gamma_indices):
            qpts = np.insert(qpts, index, [0.0, 0.0, 0.0], axis=0)
            labels.insert(index, "GAMMA")

    # ``Γ`` renders nicely as a matplotlib/KpointsData tick label.
    tick_labels = [
        (index, "\u0393" if label == "GAMMA" else label)
        for index, label in enumerate(labels)
        if label
    ]
    LOGGER.info(
        "Generated band path: %d q-points, %d high-symmetry points",
        len(qpts),
        len(tick_labels),
    )
    lattice = np.asarray(cell[0])  # real-space cell (Angstrom) for KpointsData
    return QpointPath(qpoints=qpts, labels=tick_labels, cell=lattice)


def interpolate_phonon_modes(
    force_constants: ForceConstants,
    qpoints: np.ndarray,
    *,
    asr: str | None = "reciprocal",
) -> QpointPhononModes:
    """Fourier-interpolate phonon modes at the given fractional q-points.

    ``qpoints`` is an ``(N, 3)`` array in the crystal's reciprocal basis (as
    provided by an AiiDA ``KpointsData``). This is the core
    ``ForceConstants -> QpointPhononModes`` step.
    """
    qpoints = np.asarray(qpoints)
    LOGGER.info(
        "Computing phonon modes: %d modes across %d q-points",
        force_constants.crystal.n_atoms * 3,
        len(qpoints),
    )
    # reduce_qpts=False keeps every q-point on the explicit path (matches CLI).
    return force_constants.calculate_qpoint_phonon_modes(
        qpoints, asr=asr, reduce_qpts=False
    )


def calculate_dispersion(
    force_constants: ForceConstants,
    q_spacing: float = 0.025,
    *,
    insert_gamma: bool = True,
    asr: str | None = "reciprocal",
) -> QpointPhononModes:
    """Convenience: build a band path and interpolate modes along it."""
    path = band_path_qpoints(
        force_constants.crystal.to_spglib_cell(), q_spacing, insert_gamma=insert_gamma
    )
    return interpolate_phonon_modes(force_constants, path.qpoints, asr=asr)


def default_energy_bins(
    frequencies: pint.Quantity,
    energy_spacing: pint.Quantity,
    *,
    padding_fraction: float = 0.05,
) -> pint.Quantity:
    """Compute default bin edges with asymmetric padding and fixed physical spacing.

    Parameters
    ----------
    frequencies
        Phonon frequencies as a dimensional Quantity.
    energy_spacing
        Width of each energy bin as a dimensional Quantity (e.g. ``1.0 * ureg('meV')``).
    padding_fraction
        Fractional padding based on the occupied frequency span (default: 0.05).
        Always added above the maximum frequency; added below the minimum frequency
        only if negative (imaginary modes present).

    Returns
    -------
    pint.Quantity
        Bin edges with uniform spacing in the units of ``energy_spacing``.
    """
    freqs = frequencies.to(energy_spacing.units, "spectroscopy")
    emin, emax = freqs.min(), freqs.max()

    span = max(emax - emin, energy_spacing)
    pad = padding_fraction * span

    upper = emax + pad
    lower = (emin - pad) if emin < 0 else 0

    start_idx = np.floor((lower / energy_spacing).magnitude)
    stop_idx = np.ceil((upper / energy_spacing).magnitude) + 1.0

    return np.arange(start_idx, stop_idx) * energy_spacing


def calculate_dos(
    force_constants: ForceConstants,
    q_spacing: float = 0.1,
    energy_spacing: float = 1.0,
    *,
    energy_unit: str = "meV",
    adaptive: bool = True,
    asr: str | None = "reciprocal",
) -> Spectrum1D:
    """Compute a phonon density of states by sampling a Monkhorst-Pack grid.

    Parameters
    ----------
    force_constants
        Interatomic force constants to interpolate from.
    q_spacing
        Target spacing of the sampling grid, in 1/Angstrom (finer -> denser grid).
    energy_spacing
        Width of the DOS energy bins, in ``energy_unit``.
    energy_unit
        Unit for the energy axis (e.g. ``"meV"``, ``"1/cm"``).
    adaptive
        Use adaptive broadening (per-mode widths from mode gradients) rather than
        fixed bins. Recommended; requires computing mode gradients.
    asr
        Acoustic sum rule applied during interpolation (``None`` to disable).

    Returns
    -------
    Spectrum1D
        Density of states vs energy (bin edges in ``x_data``, values in
        ``y_data``; use ``get_bin_centres()`` for matching x/y lengths).
    """
    grid = force_constants.crystal.get_mp_grid_spec(
        spacing=q_spacing * ureg("1/angstrom")
    )
    qpts = mp_grid(grid)
    LOGGER.info(
        "Sampling DOS: %dx%dx%d grid (%d q-points), adaptive=%s",
        *grid,
        len(qpts),
        adaptive,
    )
    result = force_constants.calculate_qpoint_phonon_modes(
        qpts, asr=asr, return_mode_gradients=adaptive
    )
    if adaptive:
        modes, mode_gradients = result
        mode_widths = mode_gradients_to_widths(
            mode_gradients, force_constants.crystal.cell_vectors
        )
    else:
        modes, mode_widths = result, None

    dos_bins = default_energy_bins(
        modes.frequencies, Quantity(energy_spacing, energy_unit)
    )
    return modes.calculate_dos(dos_bins, mode_widths=mode_widths)


# --- TOSCA scattering-intensity operations -------------------------------------
#
# These wrap `abinslib` (almost-isotropic incoherent INS intensities) and
# `resins` (instrument resolution functions). Like the rest of this module they
# are plain, AiiDA-free functions using only public APIs; see the reference
# pipeline (abINS_lib's TOSCA tutorial) cited in
# openspec/changes/abinslib-workflow/design.md for the calculation this mirrors.
#
# abinslib decouples cross-section weighting from intensity calculations:
# `calculate_almost_isotropic_incoherent_spectra` and
# `mantid_like_combination_spectra` return unweighted spectra, and callers
# must explicitly invoke `apply_weights` to scale intensities by neutron
# scattering cross sections (producing physical `barn * cm` units).


def calculate_thermal_displacements(
    modes: QpointPhononModes, temperature: float
) -> tuple[Displacements, pint.Quantity]:
    """Compute thermal mode/atomic displacements at a sample temperature.

    Thin wrapper over ``Displacements.from_modes`` and
    ``.to_atomic_displacements()``. The atomic displacements determine the
    Debye-Waller attenuation applied by the intensity calculations below.

    Parameters
    ----------
    modes
        Phonon frequencies and eigenvectors.
    temperature
        Sample temperature in kelvin.

    Returns
    -------
    tuple[Displacements, pint.Quantity]
        The per-mode displacement dataset and the derived per-atom
        displacement tensor (``Quantity``, shape ``(n_atoms, 3, 3)``).
    """
    mode_displacements = Displacements.from_modes(modes, Quantity(temperature, "K"))
    atomic_displacements = mode_displacements.to_atomic_displacements()
    LOGGER.info(
        "Computed thermal displacements at %s K for %d atoms",
        temperature,
        modes.crystal.n_atoms,
    )
    return mode_displacements, atomic_displacements


def calculate_scattering_q2(
    energy_transfer: pint.Quantity,
    detector_angle: float,
    final_energy: float,
    *,
    energy_unit: str = "1/cm",
) -> pint.Quantity:
    """Indirect-geometry Q² for a scattering angle and analyser final energy.

    Thin wrapper over ``abinslib.util.calculate_indirect_q2`` that takes the
    detector angle in degrees (the natural unit for describing a bank) rather
    than radians, and the final energy as a plain float in ``energy_unit``
    (matching the other TOSCA operations' unit convention) rather than a
    pre-built ``Quantity``.

    Called once per detector bank, with ``energy_transfer`` set to the mode
    frequencies for the fundamental calculation and to the output bin centres
    for the combination-mode calculation -- the two kinematic evaluations the
    reference pipeline performs.
    """
    return calculate_indirect_q2(
        energy_transfer,
        angle=np.deg2rad(detector_angle),
        final_energy=Quantity(final_energy, energy_unit),
    )


def tosca_energy_bins(
    frequencies: pint.Quantity,
    energy_spacing: pint.Quantity,
    energy_max: pint.Quantity,
    *,
    max_quantum_order: int = 2,
) -> pint.Quantity:
    """Build the TOSCA energy axis: data-sized, then clipped to the instrument.

    Reuses :func:`default_energy_bins`' padding and bin-alignment rule, sized
    from the fundamental frequencies scaled by the highest quantum order to be
    computed (combination modes extend to roughly that multiple of the
    fundamental range), then clips to whichever of the data range or
    ``energy_max`` is tighter.

    The lower end is additionally clipped at zero. Unlike a density of states,
    where a negative energy indicates a real, physically meaningful soft mode,
    TOSCA measures only energy loss from the neutron to the sample: an energy
    transfer below zero (let alone below ``-final_energy``) is kinematically
    inaccessible, and evaluating the Q² relation there produces nonsense
    (``calculate_scattering_q2`` takes a square root that goes complex). A
    q-point mesh's small numerical noise around an acoustic mode at the zone
    centre is enough to trigger asymmetric padding on the negative side, so
    this clip is not merely a corner case.
    """
    data_bins = default_energy_bins(frequencies * max_quantum_order, energy_spacing)
    zero = Quantity(0, energy_spacing.units)
    return data_bins[(data_bins >= zero) & (data_bins <= energy_max)]


def broaden_tosca_spectrum(
    spectrum: Spectrum1D | Spectrum1DCollection,
    resolution_model: str = "AbINS_v1",
) -> Spectrum1D | Spectrum1DCollection:
    """Apply TOSCA's energy-dependent resolution broadening to a spectrum.

    Broadens on the spectrum's own bin centres (``points == mesh``), so no
    rebinning takes place -- only the resolution-smeared intensity changes.
    Because ``resins``' broadening operator is linear, this gives the same
    result whether applied before or after summing lines (see
    ``group_spectra``/``broaden_spectra`` in
    :mod:`aiida_pythonjob_ins.workflows.tosca`, which rely on this).

    A collection is broadened line by line: the underlying ``resins`` model
    only accepts a single 1-D intensity array per call (see
    ``InstrumentModel.broaden``), not a 2-D stack of lines.
    """
    resolution = Instrument.from_default("TOSCA").get_resolution_function(
        resolution_model
    )
    x_mev = spectrum.get_bin_centres().to("meV").magnitude

    if isinstance(spectrum, Spectrum1DCollection):
        broadened_y = np.stack(
            [
                resolution.broaden(points=x_mev[:, None], data=line_y, mesh=x_mev)
                for line_y in spectrum.y_data.magnitude
            ]
        )
    else:
        broadened_y = resolution.broaden(
            points=x_mev[:, None], data=spectrum.y_data.magnitude, mesh=x_mev
        )

    broadened = type(spectrum)(
        x_data=spectrum.x_data,
        y_data=Quantity(broadened_y, spectrum.y_data.units),
        x_tick_labels=spectrum.x_tick_labels,
        metadata=spectrum.metadata,
    )
    LOGGER.info("Applied '%s' resolution broadening", resolution_model)
    return broadened


def interpolate_phonon_modes_on_grid(
    force_constants: ForceConstants,
    q_spacing: float = 0.1,
    *,
    asr: str | None = "reciprocal",
) -> QpointPhononModes:
    """Interpolate phonon modes on a Monkhorst-Pack grid (a powder average).

    Unlike :func:`interpolate_phonon_modes`, which evaluates a caller-supplied
    set of q-points (e.g. a high-symmetry band path), this samples the whole
    Brillouin zone the way :func:`calculate_dos` does -- the sampling
    :class:`ToscaFromForceConstantsWorkChain
    <aiida_pythonjob_ins.workflows.tosca.ToscaFromForceConstantsWorkChain>` needs.
    The almost-isotropic incoherent approximation disregards actual q-point
    *positions* (see the reference pipeline's kinematic treatment in
    :func:`calculate_tosca_spectrum`), but still needs a representative *density*
    of modes across the zone, exactly as a DOS does.

    Parameters
    ----------
    force_constants
        Interatomic force constants to interpolate from.
    q_spacing
        Target spacing of the sampling grid, in 1/Angstrom (finer -> denser grid).
    asr
        Acoustic sum rule applied during interpolation (``None`` to disable).
    """
    grid = force_constants.crystal.get_mp_grid_spec(
        spacing=q_spacing * ureg("1/angstrom")
    )
    qpts = mp_grid(grid)
    LOGGER.info(
        "Interpolating modes on a %dx%dx%d grid (%d q-points) for TOSCA",
        *grid,
        len(qpts),
    )
    return force_constants.calculate_qpoint_phonon_modes(
        qpts, asr=asr, reduce_qpts=False
    )


def calculate_tosca_spectrum(
    modes: QpointPhononModes,
    temperature: float = 10.0,
    energy_spacing: float = 10.0,
    energy_max: float = 4000.0,
    detector_angles: list[float] | None = None,
    final_energy: float = 32.0,
    energy_unit: str = "1/cm",
) -> Spectrum1DCollection:
    """Compute the full, ungrouped TOSCA intensity line set from phonon modes.

    Combines fundamental (one-phonon) and combination (two-phonon) intensities
    in the almost-isotropic incoherent approximation, for every requested
    detector bank, into a single collection with one line per atom, quantum
    order and detector angle -- mirroring the reference pipeline's
    ``fundamentals + second_order`` sum, repeated per bank.

    Cross-section weighting is applied explicitly via ``apply_weights`` to the
    raw (fundamentals + combinations) collection before grouping, producing
    physical intensities in cross-section-weighted units (``barn * cm`` or
    ``barn / energy``).

    Parameters
    ----------
    modes
        Phonon frequencies and eigenvectors (e.g. from a molecular-crystal
        calculation; the almost-isotropic approximation assumes hydrogenous,
        largely incoherent scattering).
    temperature
        Sample temperature in kelvin, governing the Debye-Waller attenuation.
    energy_spacing, energy_max
        Energy axis bin width and instrument-range cutoff, in ``energy_unit``.
        See :func:`tosca_energy_bins`.
    detector_angles
        Scattering angles in degrees, one per detector bank to evaluate.
        Defaults to TOSCA's backward (135°) and forward (45°) banks.
    final_energy
        Analyser-fixed final neutron energy, in ``energy_unit``.
    energy_unit
        Unit for ``energy_spacing``, ``energy_max`` and ``final_energy``.
        TOSCA results are conventionally reported in wavenumbers.

    Returns
    -------
    Spectrum1DCollection
        One line per (atom, quantum order, detector angle), each carrying that
        triple in its ``line_data`` metadata under ``atom_symbol``,
        ``quantum_order`` and ``detector_angle``. Intensities are cross-section
        weighted with units of ``barn * cm`` (or ``barn / energy``). Not yet
        grouped or broadened.
    """
    if detector_angles is None:
        detector_angles = [135.0, 45.0]

    mode_displacements, atomic_displacements = calculate_thermal_displacements(
        modes, temperature
    )
    bins = tosca_energy_bins(
        modes.frequencies,
        Quantity(energy_spacing, energy_unit),
        Quantity(energy_max, energy_unit),
    )
    bin_centres = (bins[1:] + bins[:-1]) / 2

    LOGGER.info(
        "Computing TOSCA spectrum: %d atoms, %d banks, %d energy bins",
        modes.crystal.n_atoms,
        len(detector_angles),
        len(bins) - 1,
    )

    per_bank_spectra = []
    for detector_angle in detector_angles:
        fundamental_q2 = calculate_scattering_q2(
            modes.frequencies, detector_angle, final_energy, energy_unit=energy_unit
        )
        combination_q2 = calculate_scattering_q2(
            bin_centres, detector_angle, final_energy, energy_unit=energy_unit
        )
        fundamentals = calculate_almost_isotropic_incoherent_spectra(
            modes=modes,
            mode_displacements=mode_displacements,
            atomic_displacements=atomic_displacements,
            nominal_q2=fundamental_q2,
            bins=bins,
        )
        combinations = mantid_like_combination_spectra(
            modes, mode_displacements, atomic_displacements, combination_q2, bins
        )

        # Apply cross-section weights before grouping. The raw
        # (fundamentals + combinations) collection carries `atom_symbol` and
        # `mass` metadata from `iter_atom_info(modes.crystal)`, which
        # `apply_weights` uses to scale intensities by the corresponding
        # neutron scattering cross sections.
        #
        # Grouping on (atom_index, quantum_order) merges q-point duplicates
        # while keeping fundamentals (order 1) and combinations (order 2+)
        # separate. Grouping on atom_index alone would incorrectly sum across
        # quantum orders.
        raw_bank = fundamentals + combinations
        weighted_bank = apply_weights(raw_bank, key="scattering_cross_section")
        bank_spectrum = weighted_bank.group_by("atom_index", "quantum_order")
        for line_data in bank_spectrum.metadata["line_data"]:
            line_data["detector_angle"] = detector_angle
        per_bank_spectra.append(bank_spectrum)

    spectrum = per_bank_spectra[0]
    for extra in per_bank_spectra[1:]:
        spectrum = spectrum + extra
    return spectrum
