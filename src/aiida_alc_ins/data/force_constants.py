"""AiiDA Data node wrapping a Euphonic ``ForceConstants`` object.

``ForceConstants`` is the primary *input* object for lattice-dynamics workflows:
it holds the interatomic force constants (plus crystal + optional dipole data)
from which phonons at arbitrary q-points are interpolated.
https://euphonic.readthedocs.io/en/stable/force-constants.html
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Self

from euphonic import ForceConstants

from .base import EuphonicJSONData
from .mixins import CrystalStructureMixin


class ForceConstantsData(CrystalStructureMixin, EuphonicJSONData):
    """Store a Euphonic ``ForceConstants`` object as an AiiDA node."""

    _euphonic_cls: ClassVar[type] = ForceConstants

    def get_force_constants(self) -> ForceConstants:
        """Return the wrapped :class:`euphonic.ForceConstants`."""
        return self.get_object()

    @classmethod
    def from_castep(cls, filepath: str | Path) -> Self:
        """Build a node by reading a CASTEP ``.castep_bin``/``.check`` file.

        Uses the public reader ``ForceConstants.from_castep``.
        """
        return cls(ForceConstants.from_castep(str(filepath)))

    @classmethod
    def from_phonopy(cls, **kwargs) -> Self:
        """Build a node from Phonopy output via ``ForceConstants.from_phonopy``.

        Requires the optional ``phonopy`` extra. Keyword arguments are forwarded
        (e.g. ``path``, ``summary_name``, ``fc_name``).
        """
        return cls(ForceConstants.from_phonopy(**kwargs))
