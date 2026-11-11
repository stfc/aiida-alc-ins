"""Spec-only tests for the abstract base WorkChains (no process run).

These verify the ``JobDispatchWorkChain`` and ``FromForceConstantsWorkChain``
specs in isolation: each base builds its own spec, and the two feature sets are
independent.
"""

from __future__ import annotations

from aiida_alc_ins.workflows.base import (
    FromForceConstantsWorkChain,
    JobDispatchWorkChain,
)
from aiida_alc_ins.workflows.tosca import ToscaFromModesWorkChain


def test_job_dispatch_spec_has_code_and_options():
    """``JobDispatchWorkChain`` declares ``code`` and ``options`` and exit code 400."""
    spec = JobDispatchWorkChain.spec()
    assert "code" in spec.inputs
    assert "options" in spec.inputs
    assert "force_constants" not in spec.inputs
    assert spec.exit_codes.ERROR_SUB_PROCESS_FAILED.status == 400


def test_from_force_constants_spec_has_namespace():
    """``FromForceConstantsWorkChain`` exposes a required namespace."""
    spec = FromForceConstantsWorkChain.spec()
    namespace = spec.inputs["force_constants"]
    assert namespace.required is True
    assert "castep_file" in namespace
    assert "node" in namespace
    # The dispatch plumbing lives on the other base.
    assert "code" not in spec.inputs
    assert "options" not in spec.inputs
    assert spec.exit_codes.ERROR_SUB_PROCESS_FAILED_FORCE_CONSTANTS.status == 402


def test_tosca_from_modes_redeclares_exit_code_400():
    """``ToscaFromModesWorkChain`` keeps its specific 400 message.

    It re-declares ``ERROR_SUB_PROCESS_FAILED`` with its own message, distinct
    from the generic one ``JobDispatchWorkChain`` provides.
    """
    tosca_code = ToscaFromModesWorkChain.exit_codes.ERROR_SUB_PROCESS_FAILED
    dispatch_code = JobDispatchWorkChain.exit_codes.ERROR_SUB_PROCESS_FAILED
    assert tosca_code.status == 400
    assert tosca_code.message == "The intensity PythonJob did not finish successfully."
    assert tosca_code.message != dispatch_code.message
