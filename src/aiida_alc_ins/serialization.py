"""Bridges between Euphonic objects and our AiiDA Data nodes for aiida-pythonjob.

``aiida-pythonjob`` converts a plain Python function into an AiiDA process. To do
so it must (de)serialize the function's inputs/outputs to/from AiiDA nodes:

* **serializers** map a *Python type* (``module.ClassName``) to a callable that
  returns an ``aiida.orm.Data`` node. Our Data classes already accept the Euphonic
  object in their constructor (``ForceConstantsData(fc, user=...)``), so the class
  itself is a valid serializer.
* **deserializers** map an *AiiDA node type* back to the Python object the function
  expects.

We pass these dicts explicitly via ``prepare_pythonjob_inputs(serializers=...,
deserializers=...)`` rather than registering extra entry points, keeping the
``aiida.data`` entry points clean (one per Data class).
See https://aiida-pythonjob.readthedocs.io/ (data serialization).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from aiida.orm import KpointsData, Node
from euphonic import ForceConstants, QpointPhononModes, Spectrum1D, Spectrum1DCollection

from .conversions import spectrum1d_to_xydata, spectrum_collection_to_xydata
from .data import ForceConstantsData, QpointPhononModesData


def _serializer_key(cls: type) -> str:
    """Registry key exactly as ``aiida-pythonjob`` computes it for a runtime object.

    ``aiida-pythonjob`` looks up a returned object's serializer by
    ``f"{type(obj).__module__}.{type(obj).__name__}"``. Deriving the key from the
    imported class itself, rather than writing the string by hand, means the key
    follows the class if it is relocated upstream (as ``Spectrum1DCollection`` is
    relative to ``Spectrum1D`` -- see
    openspec/changes/archive/2026-08-24-abinslib-workflow/design.md,
    "10. Serializer keys are derived from the classes, not hand-written"). A
    stale hand-written key would not raise: the lookup would simply miss and
    silently fall through to a generic ``JsonableData``/``PickledData`` fallback.
    """
    return f"{cls.__module__}.{cls.__name__}"


# See "Serializer and Deserializer Architecture" in docs/source/design_notes.rst
# for the full (de)serialization model and conversion map.
# Python type (module.ClassName) -> dotted path of a callable returning a Data node.
EUPHONIC_SERIALIZERS: dict[str, str] = {
    _serializer_key(ForceConstants): (
        "aiida_alc_ins.data.force_constants.ForceConstantsData"
    ),
    _serializer_key(QpointPhononModes): (
        "aiida_alc_ins.data.qpoint_phonon_modes.QpointPhononModesData"
    ),
    # A DOS (or other Spectrum1D) becomes a native XyData.
    _serializer_key(Spectrum1D): (
        "aiida_alc_ins.serialization.spectrum1d_to_xydata_node"
    ),
    # A TOSCA spectrum (or any Spectrum1DCollection) becomes one native XyData
    # with one y array per line (see conversions.spectrum_collection_to_xydata).
    _serializer_key(Spectrum1DCollection): (
        "aiida_alc_ins.serialization.spectrum_collection_to_xydata_node"
    ),
}

# AiiDA node type (module.ClassName) -> dotted path of a callable returning the object.
EUPHONIC_DESERIALIZERS: dict[str, str] = {
    "aiida_alc_ins.data.force_constants.ForceConstantsData": (
        "aiida_alc_ins.serialization.force_constants_from_node"
    ),
    "aiida_alc_ins.data.qpoint_phonon_modes.QpointPhononModesData": (
        "aiida_alc_ins.serialization.qpoint_phonon_modes_from_node"
    ),
    # A KpointsData input to the interpolation op deserializes to a q-points array.
    "aiida.orm.nodes.data.array.kpoints.KpointsData": (
        "aiida_alc_ins.serialization.kpoints_data_to_qpoints"
    ),
}


def kpoints_data_to_qpoints(node: KpointsData) -> np.ndarray:
    """Deserializer: KpointsData node -> fractional q-points array."""
    return node.get_kpoints()


def spectrum1d_to_xydata_node(spectrum: Any, user: Any = None) -> Any:  # noqa: ARG001
    """Serializer: euphonic Spectrum1D -> XyData (``user`` per the call convention)."""
    return spectrum1d_to_xydata(spectrum)


def spectrum_collection_to_xydata_node(spectrum: Any, user: Any = None) -> Any:  # noqa: ARG001
    """Serializer: euphonic Spectrum1DCollection -> XyData (``user`` per convention)."""
    return spectrum_collection_to_xydata(spectrum)


def force_constants_from_node(node: ForceConstantsData) -> Any:
    """Deserializer: ForceConstantsData node -> euphonic.ForceConstants."""
    return node.get_force_constants()


def qpoint_phonon_modes_from_node(node: QpointPhononModesData) -> Any:
    """Deserializer: QpointPhononModesData node -> euphonic.QpointPhononModes."""
    return node.get_modes()


def _assert_node(value: Node) -> None:
    """Guard used in tests to confirm serialization produced a Data node."""
    if not isinstance(value, Node):
        msg = f"Expected an AiiDA Node, got {type(value).__name__}."
        raise TypeError(msg)
