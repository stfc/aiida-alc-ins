"""Assertion helpers shared by the test modules.

Euphonic quantities carry units, and ``np.testing.assert_allclose`` on a quantity
strips them with a warning. These helpers therefore compare quantities in base
units, so that two values agree physically even when their unit expressions
differ.
"""

from __future__ import annotations

import numpy as np


def assert_quantity_allclose(actual, expected, **kwargs) -> None:
    """Assert two Euphonic quantities have the same dimensions and value.

    Both quantities are converted to base units before the comparison. A mismatch
    in dimensions fails the unit check; a value difference fails the
    ``assert_allclose`` check. Extra keyword arguments (``rtol``, ``atol``) are
    passed to ``np.testing.assert_allclose``.
    """
    actual_base = actual.to_base_units()
    expected_base = expected.to_base_units()
    assert actual_base.units == expected_base.units, (
        f"Units differ: {actual.units} vs {expected.units}"
    )
    np.testing.assert_allclose(actual_base.magnitude, expected_base.magnitude, **kwargs)


def assert_optional_quantity_allclose(actual, expected, **kwargs) -> None:
    """Assert two optional quantities are both ``None`` or both match."""
    if expected is None:
        assert actual is None
    else:
        assert actual is not None
        assert_quantity_allclose(actual, expected, **kwargs)


def assert_equivalent_force_constants(actual, expected, **kwargs) -> None:
    """Assert two ``euphonic.ForceConstants`` describe the same material.

    Compares the force constants, the cell vectors, the atomic positions and types,
    and the Born and dielectric data (both absent, or both matching).
    """
    assert_quantity_allclose(actual.force_constants, expected.force_constants, **kwargs)
    assert_quantity_allclose(
        actual.crystal.cell_vectors, expected.crystal.cell_vectors, **kwargs
    )
    np.testing.assert_allclose(actual.crystal.atom_r, expected.crystal.atom_r, **kwargs)
    assert list(actual.crystal.atom_type) == list(expected.crystal.atom_type)
    assert_optional_quantity_allclose(actual.born, expected.born, **kwargs)
    assert_optional_quantity_allclose(actual.dielectric, expected.dielectric, **kwargs)
