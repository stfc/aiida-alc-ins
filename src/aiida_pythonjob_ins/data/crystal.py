"""AiiDA Data node wrapping a Euphonic ``Crystal`` object.

``Crystal`` is euphonic's crystal-structure representation (cell, atom positions,
species, masses). This node is the bridge between euphonic's representation and
AiiDA's native ``StructureData``, and the single home for those conversions.
https://euphonic.readthedocs.io/en/stable/
"""

from __future__ import annotations

from typing import ClassVar

from typing_extensions import Self

from aiida.orm import StructureData
from euphonic import Crystal

from aiida_pythonjob_ins.conversions import (
    crystal_to_structure,
    structure_to_crystal,
)

from .base import EuphonicJSONData


class EuphonicCrystalData(EuphonicJSONData):
    """Store a Euphonic ``Crystal`` object as an AiiDA node.

    Note: this deliberately does *not* use ``CrystalStructureMixin`` -- the wrapped
    object *is* the crystal (it has no ``.crystal`` attribute), so ``to_structure``
    is defined directly here.
    """

    _euphonic_cls: ClassVar[type] = Crystal

    def get_crystal(self) -> Crystal:
        """Return the wrapped :class:`euphonic.Crystal`."""
        return self.get_object()

    def to_structure(self) -> StructureData:
        """Convert to a native AiiDA ``StructureData`` (no ASE)."""
        return crystal_to_structure(self.get_crystal())

    def to_spglib_cell(self) -> tuple:
        """Return the spglib ``(lattice, positions, numbers)`` tuple.

        Delegates to euphonic's own ``Crystal.to_spglib_cell``.
        """
        return self.get_crystal().to_spglib_cell()

    @classmethod
    def from_structure(cls, structure: StructureData) -> Self:
        """Build a node from a native AiiDA ``StructureData``."""
        return cls(structure_to_crystal(structure))
