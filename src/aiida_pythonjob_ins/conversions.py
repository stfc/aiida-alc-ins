"""Mappings between Euphonic objects and AiiDA's native materials-science types.

AiiDA ships domain data types for reciprocal-space data
(https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/data_types.html#materials-science-data-types):

* ``KpointsData`` -- k-/q-point positions (+ optional labels + cell). We use it as
  the q-point *specification* for Fourier interpolation, and as the natural
  representation of a phonon band path.
* ``BandsData`` (a ``KpointsData`` subclass) -- band energies on those points. A
  Euphonic ``QpointPhononModes`` is essentially ``BandsData`` (frequencies) plus
  eigenvectors, so we build a ``BandsData`` by *composition* and keep the
  eigenvectors in our own ``QpointPhononModesData``.

Using ``BandsData`` also unlocks existing AiiDA plotting, e.g.
``bands.show_mpl()`` pops up a matplotlib band-structure plot without any
AiiDALab dependency.

**These are plain converter functions, deliberately NOT calcfunctions.** They
are the reusable "verbs" that *produce* an object (an AiiDA node or a euphonic
object), called from contexts that each preclude the decorator: inside the
workflow's calcfunctions (``generate_band_path``, ``assemble_bands``) and inside
Data-class methods (``to_structure``/``to_kpoints``/``to_bands``), which must work
without any engine. Several also take/return non-node objects (euphonic
``Crystal``, ``ndarray``), which a calcfunction could not accept. Provenance is
recorded one level up, by the ``@calcfunction``/``PythonJob`` wrappers in
:mod:`aiida_pythonjob_ins.workflows` that call these helpers.

(The reverse direction -- node -> plain Python for aiida-pythonjob *inputs* -- is
a deserialization concern and lives in :mod:`aiida_pythonjob_ins.serialization`.)
"""

from __future__ import annotations

from typing import Any

import numpy as np
from aiida.orm import BandsData, KpointsData, StructureData, XyData
from euphonic import Crystal, Spectrum1DCollection, ureg


def crystal_to_structure(crystal: Crystal) -> StructureData:
    """Convert a Euphonic ``Crystal`` to a native AiiDA ``StructureData``.

    Single source of truth for the Crystal -> StructureData direction (used by
    ``EuphonicCrystalData`` and by ``CrystalStructureMixin.to_structure``). Uses
    AiiDA's native API only -- no ASE. Euphonic stores fractional positions;
    ``StructureData`` wants Cartesian. Masses are carried over for fidelity.
    """
    cell = crystal.cell_vectors.to("angstrom").magnitude
    cartesian = np.asarray(crystal.atom_r) @ cell
    masses = crystal.atom_mass.to("amu").magnitude

    # A euphonic Crystal is always a 3D-periodic lattice, so set pbc explicitly
    # rather than relying on StructureData's default.
    structure = StructureData(cell=cell.tolist(), pbc=(True, True, True))
    for symbol, position, mass in zip(
        crystal.atom_type, cartesian, masses, strict=True
    ):
        structure.append_atom(
            position=position.tolist(), symbols=str(symbol), mass=float(mass)
        )
    return structure


def structure_to_crystal(structure: StructureData) -> Crystal:
    """Convert a native AiiDA ``StructureData`` to a Euphonic ``Crystal``.

    The reverse of :func:`crystal_to_structure`. ``Crystal`` requires atom masses,
    which ``StructureData`` carries on its kinds.
    """
    cell = np.array(structure.cell)
    inverse_cell = np.linalg.inv(cell)
    kinds = {kind.name: kind for kind in structure.kinds}
    atom_r = np.array(
        [np.array(site.position) @ inverse_cell for site in structure.sites]
    )
    atom_type = np.array([kinds[site.kind_name].symbol for site in structure.sites])
    atom_mass = np.array([kinds[site.kind_name].mass for site in structure.sites])
    return Crystal(cell * ureg("angstrom"), atom_r, atom_type, atom_mass * ureg("amu"))


def structure_to_spglib_cell(
    structure: StructureData,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert a ``StructureData`` to a spglib/seekpath cell tuple.

    Returns ``(lattice, positions, numbers)`` by reusing Euphonic's
    ``Crystal.to_spglib_cell`` (rather than re-deriving the species numbering by
    hand).
    """
    return structure_to_crystal(structure).to_spglib_cell()


def qpoints_to_kpoints_data(
    qpoints: np.ndarray,
    cell: np.ndarray,
    labels: list[tuple[int, str]] | None = None,
) -> KpointsData:
    """Build a ``KpointsData`` from fractional q-points, a cell and labels."""
    kpoints = KpointsData()
    kpoints.set_cell(np.asarray(cell))
    kpoints.set_kpoints(np.asarray(qpoints), cartesian=False, labels=labels)
    return kpoints


def spectrum1d_to_xydata(spectrum: Any) -> XyData:
    """Convert a Euphonic ``Spectrum1D`` (e.g. a DOS) to a native ``XyData``.

    Uses ``get_bin_centres()`` so the x and y arrays have matching lengths
    (``Spectrum1D`` stores bin *edges* in ``x_data`` when it is histogram-like).
    Unit labels are recorded on the ``XyData`` arrays.
    """
    x_values = spectrum.get_bin_centres().magnitude
    x_unit = f"{spectrum.x_data.units:~}"
    y_unit = f"{spectrum.y_data.units:~}"

    xy = XyData()
    xy.set_x(x_values, "energy", x_unit)
    xy.set_y(spectrum.y_data.magnitude, "density_of_states", y_unit)
    return xy


# Metadata keys rendered without decoration in a legend label, in the order
# they are combined when more than one varies at once (most specific last, so
# e.g. "C (order 2)" reads as "carbon, second-order combination").
_LABEL_KEY_ORDER = ("atom_symbol", "quantum_order", "detector_angle")

# Present on every line but not meaningful in a legend: atom_symbol already
# identifies the atom for plotting purposes, and abinslib's `atom_index` merely
# distinguishes same-element atoms from each other, which would make every line
# "vary" and defeat the point of only labelling what differs usefully.
_LABEL_EXCLUDED_KEYS = frozenset({"atom_index"})


def _format_label_value(key: str, value: Any) -> str:
    """Render one metadata key/value pair for use in a legend label."""
    if key == "quantum_order":
        return f"order {value}"
    if key == "detector_angle":
        return f"{value}\N{DEGREE SIGN}"
    if key == "mass":
        # Round to avoid floating-point noise in label display
        return f"{float(value):.6g}"
    return str(value)


def spectrum_collection_labels(collection: Spectrum1DCollection) -> list[str]:
    """Derive a concise, human-readable legend label for each line of a collection.

    Only the ``line_data`` metadata keys that actually differ between lines are
    used, so a collection already grouped down to one line -- where every key is
    common rather than varying -- is labelled ``"Total"`` instead of repeating
    metadata that no longer distinguishes anything.

    ``atom_symbol``, if it varies, is rendered bare (``"C"``); other varying keys
    are appended in parentheses (``"C (order 2)"``) in the fixed order
    atom_symbol/quantum_order/detector_angle, with any other, unrecognised keys
    appended afterwards in sorted order for determinism. This is deliberately a
    plotting convenience, not a lossless encoding -- the full metadata travels
    separately (see :func:`spectrum_collection_to_xydata`).
    """
    line_data: list[dict[str, Any]] = list(
        collection.metadata.get("line_data") or [{}] * len(collection)
    )
    if not line_data:
        return []

    all_keys = {key for line in line_data for key in line} - _LABEL_EXCLUDED_KEYS
    varying = {
        key for key in all_keys if len({line.get(key) for line in line_data}) > 1
    }
    if not varying:
        return ["Total"] * len(line_data)

    ordered_keys = [key for key in _LABEL_KEY_ORDER if key in varying]
    ordered_keys += sorted(varying - set(ordered_keys))

    labels = []
    for line in line_data:
        parts = [
            _format_label_value(key, line[key]) for key in ordered_keys if key in line
        ]
        if not parts:
            label = "Total"
        elif ordered_keys[0] == "atom_symbol" and len(parts) > 1:
            label = f"{parts[0]} ({', '.join(parts[1:])})"
        else:
            label = ", ".join(parts).capitalize()
        labels.append(label)
    return labels


def spectrum_collection_to_xydata(collection: Spectrum1DCollection) -> XyData:
    """Convert a Euphonic ``Spectrum1DCollection`` to a native ``XyData``.

    Like :func:`spectrum1d_to_xydata`, one x array of bin centres is shared by
    every line; unlike it, there are several y arrays (one per line), and the
    collection's metadata -- which is what actually distinguishes the lines --
    would otherwise be lost. It is preserved on the node as two attributes:

    * ``spectrum_metadata`` -- the metadata common to the whole collection;
    * ``spectrum_line_data`` -- the list of per-line metadata dicts.

    Both are ordinary AiiDA node attributes: JSON-serialisable Python values
    attached before the node is stored, becoming immutable once it is (matching
    the provenance guarantee AiiDA gives every stored node). They sit alongside
    ``XyData``'s own attributes without collision (its arrays are namespaced
    under an ``array|`` prefix). See :func:`xydata_to_spectrum_collection` for
    the reverse direction, which is what makes this round trip reversible.

    Each y array is additionally named with a concise label from
    :func:`spectrum_collection_labels`, so ``for name, y, unit in xy.get_y()``
    is directly plottable without parsing the attached metadata.
    """
    x_values = collection.get_bin_centres().magnitude
    x_unit = f"{collection.x_data.units:~}"
    y_unit = f"{collection.y_data.units:~}"

    line_data = list(collection.metadata.get("line_data") or [{}] * len(collection))
    common_metadata = {
        key: value for key, value in collection.metadata.items() if key != "line_data"
    }
    labels = spectrum_collection_labels(collection)

    xy = XyData()
    xy.set_x(x_values, "energy", x_unit)
    y_rows = list(collection.y_data.magnitude)
    xy.set_y(y_rows, labels, [y_unit] * len(y_rows))
    xy.base.attributes.set("spectrum_metadata", common_metadata)
    xy.base.attributes.set("spectrum_line_data", line_data)
    return xy


def xydata_to_spectrum_collection(xy: XyData) -> Spectrum1DCollection:
    """Convert a native ``XyData`` back to a Euphonic ``Spectrum1DCollection``.

    The reverse of :func:`spectrum_collection_to_xydata`: rebuilds the
    collection's metadata from the ``spectrum_metadata``/``spectrum_line_data``
    node attributes, so the recovered collection can be grouped, selected and
    summed by that metadata exactly as the original could -- which is what lets
    the grouping step in
    :mod:`aiida_pythonjob_ins.workflows.tosca` operate on data read back from
    the graph rather than needing the original Python object.

    Bin *centres* are recovered, not edges (see the module-level note on
    :func:`spectrum1d_to_xydata`): the resulting collection is a point spectrum,
    which is sufficient for grouping, summing and broadening but not for exact
    rebinning.
    """
    _, x_values, x_unit = xy.get_x()
    y_entries = xy.get_y()

    common_metadata = xy.base.attributes.get("spectrum_metadata", {})
    line_data = xy.base.attributes.get("spectrum_line_data", [{}] * len(y_entries))

    y_values = np.stack([values for _, values, _ in y_entries])
    (_, _, y_unit) = y_entries[0]

    return Spectrum1DCollection(
        x_data=np.asarray(x_values) * ureg(x_unit),
        y_data=y_values * ureg(y_unit),
        metadata={**common_metadata, "line_data": line_data},
    )


def modes_to_bands_data(
    modes: Any,
    kpoints: KpointsData | None = None,
) -> BandsData:
    """Compose a ``BandsData`` from Euphonic ``QpointPhononModes``.

    ``BandsData`` is a *join*: q-points + cell + high-symmetry labels (from the
    path) plus frequencies (from ``modes``); neither Euphonic class holds all of
    it (``QpointPhononModes`` has no labels; ``Spectrum1DCollection`` has no
    3-D q-points/eigenvectors).

    Parameters
    ----------
    modes
        A Euphonic ``QpointPhononModes`` object (supplies q-points + frequencies).
    kpoints
        Optional ``KpointsData`` providing the exact q-point positions *and*
        high-symmetry labels (e.g. the path used to compute ``modes``). If given,
        its q-points and cell are **validated** against ``modes`` (a mismatch
        means path and modes are inconsistent). If omitted, positions come from
        ``modes`` and labels fall back to Euphonic's automatic tick labels
        (``QpointPhononModes.get_dispersion().x_tick_labels``).
    """
    cell = modes.crystal.cell_vectors.to("angstrom").magnitude

    if kpoints is not None:
        _validate_kpoints_match_modes(kpoints, modes, cell)
        positions = kpoints.get_kpoints()
        labels = kpoints.labels
    else:
        positions = modes.qpts
        # Euphonic derives tick labels heuristically from the q-point coordinates.
        labels = modes.get_dispersion().x_tick_labels

    bands = BandsData()
    bands.set_cell(cell)
    bands.set_kpoints(positions, cartesian=False, labels=labels)
    # Phonon frequencies play the role of "band energies"; keep them in meV.
    bands.set_bands(modes.frequencies.to("meV").magnitude, units="meV")
    return bands


def _validate_kpoints_match_modes(
    kpoints: KpointsData, modes: Any, cell: np.ndarray
) -> None:
    """Raise if a ``KpointsData`` path is inconsistent with the phonon modes."""
    if not np.allclose(kpoints.get_kpoints(), modes.qpts):
        msg = (
            "KpointsData q-points do not match the phonon modes' q-points; "
            "the band path and the computed modes are inconsistent."
        )
        raise ValueError(msg)
    if not np.allclose(np.asarray(kpoints.cell), cell):
        msg = (
            "KpointsData cell does not match the phonon modes' crystal cell; "
            "q-point fractional coordinates would refer to a different lattice."
        )
        raise ValueError(msg)
