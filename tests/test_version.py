"""Tests that the package version is reported consistently and kept in provenance."""

from __future__ import annotations

import tomllib
from importlib.metadata import version
from pathlib import Path

from aiida.engine import run_get_node
from euphonic import ForceConstants

import aiida_alc_ins
from aiida_alc_ins.data import ForceConstantsData
from aiida_alc_ins.workflows.force_constants import ForceConstantsWorkChain


def test_version_matches_declared_and_installed():
    """``__version__`` is the version declared in ``pyproject.toml`` and installed.

    Comparing with the declaration also catches an installed environment that is
    stale after a version change.
    """
    pyproject = Path(__file__).parents[1] / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text())["project"]["version"]
    assert aiida_alc_ins.__version__ == declared
    assert version("aiida-alc-ins") == declared


def test_provenance_records_plugin_version(aiida_profile, quartz_castep_bin):
    """A workflow run records ``__version__`` as its process's plugin version."""
    fc_node = ForceConstantsData(ForceConstants.from_castep(quartz_castep_bin))

    _, node = run_get_node(ForceConstantsWorkChain, node=fc_node)

    assert node.is_finished_ok, node.exit_status
    recorded = node.base.attributes.get("version")["plugin"]
    assert recorded == aiida_alc_ins.__version__
