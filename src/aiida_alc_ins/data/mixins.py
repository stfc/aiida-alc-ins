"""Mixins for the Euphonic-wrapping Data classes.

Kept separate from the JSON-storage base (:class:`EuphonicJSONData`) so that a
capability like ``to_structure()`` is only present on Data classes that actually
wrap an object with a ``.crystal`` (e.g. ``ForceConstants``,
``QpointPhononModes``) -- and not, say, a future ``Spectrum1DCollectionData``,
which has no crystal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from aiida.orm import StructureData

from aiida_alc_ins.conversions import crystal_to_structure


@runtime_checkable
class SupportsToStructure(Protocol):
    """Structural type for a node that can yield its crystal as a StructureData.

    Used to type the generic ``extract_structure`` calcfunction.
    """

    def to_structure(self) -> StructureData: ...


class CrystalStructureMixin:
    """Add ``to_structure()`` to a Data class wrapping an object with ``.crystal``.

    Mix in *alongside* :class:`EuphonicJSONData` (which provides ``get_object()``),
    e.g. ``class ForceConstantsData(CrystalStructureMixin, EuphonicJSONData)``.
    """

    if TYPE_CHECKING:
        # Provided at runtime by the host Data class (EuphonicJSONData); declared
        # here only so type checkers know the mixin relies on it.
        def get_object(self) -> Any: ...

    def to_structure(self) -> StructureData:
        """Extract the wrapped object's ``.crystal`` as a native ``StructureData``.

        Delegates to :func:`~aiida_alc_ins.conversions.crystal_to_structure`
        (the single Crystal -> StructureData converter).
        """
        return crystal_to_structure(self.get_object().crystal)
