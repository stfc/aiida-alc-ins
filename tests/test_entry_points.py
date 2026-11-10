"""Tests for plugin entry-point registration.

Note: Entry-point metadata is written at install time, so a stale editable install
can make these tests pass or fail independently of edits to pyproject.toml until
reinstalled.
"""

from __future__ import annotations

from importlib.metadata import distribution
from inspect import isclass

import pytest
from aiida.plugins import DataFactory, WorkflowFactory

from aiida_pythonjob_ins.data import (
    EuphonicCrystalData,
    ForceConstantsData,
    QpointPhononModesData,
)
from aiida_pythonjob_ins.workflows import (
    DispersionWorkChain,
    DosWorkChain,
    ForceConstantsWorkChain,
    ToscaFromForceConstantsWorkChain,
    ToscaFromModesWorkChain,
)


@pytest.mark.parametrize(
    ("entry_point_name", "expected_class"),
    [
        ("pythonjob_ins.crystal", EuphonicCrystalData),
        ("pythonjob_ins.force_constants", ForceConstantsData),
        ("pythonjob_ins.qpoint_phonon_modes", QpointPhononModesData),
    ],
)
def test_data_plugin_registration(aiida_profile, entry_point_name, expected_class):
    """Data entry points resolve to their expected classes via DataFactory."""
    resolved_class = DataFactory(entry_point_name)
    assert resolved_class is expected_class


@pytest.mark.parametrize(
    ("entry_point_name", "expected_class"),
    [
        ("pythonjob_ins.force_constants", ForceConstantsWorkChain),
        ("pythonjob_ins.dispersion", DispersionWorkChain),
        ("pythonjob_ins.dos", DosWorkChain),
        ("pythonjob_ins.tosca_from_modes", ToscaFromModesWorkChain),
        (
            "pythonjob_ins.tosca_from_force_constants",
            ToscaFromForceConstantsWorkChain,
        ),
    ],
)
def test_workflow_plugin_registration(aiida_profile, entry_point_name, expected_class):
    """Workflow entry points resolve to their expected classes via WorkflowFactory."""
    resolved_class = WorkflowFactory(entry_point_name)
    assert resolved_class is expected_class


def test_every_declared_entry_point_loads():
    """Every entry point the distribution declares in the AiiDA groups loads as a class.

    Driven by the installed distribution's metadata rather than the hand-written
    lists above, so a newly declared entry point is covered without editing this
    file.
    """
    declared = [
        entry_point
        for entry_point in distribution("aiida-alc-ins").entry_points
        if entry_point.group in {"aiida.data", "aiida.workflows"}
    ]
    assert declared

    for entry_point in declared:
        loaded = entry_point.load()
        assert isclass(loaded), entry_point.name
