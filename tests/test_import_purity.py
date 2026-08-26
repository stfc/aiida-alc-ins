"""Verify that the operations import chain stays free of AiiDA.

This test runs in a subprocess with AIIDA_PATH removed, because the test session
already imports and configures AiiDA before collection (see conftest.py). An
in-session check would be vacuous: 171 aiida.* modules are already loaded.

The subprocess observes its own imports using a recording meta_path finder that
does not block imports, allowing it to detect violations and report the import
chain that caused them.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_operations_import_purity():
    """The operations module and its import chain do not import AiiDA.

    This test launches a subprocess with AIIDA_PATH removed, imports the
    operations module, calls one operation, and verifies no AiiDA modules were
    loaded at any point.
    """
    # Remove AIIDA_PATH from child environment
    env = dict(os.environ)
    env.pop("AIIDA_PATH", None)

    # Run the child process script
    child_script = Path(__file__).with_name("_check_operations_import_purity.py")
    result = subprocess.run(
        [sys.executable, str(child_script)],
        capture_output=True,
        text=True,
        env=env,
        cwd=Path(__file__).parent,  # Run from tests/ directory
        check=False,
    )

    # Parse the JSON output
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(
            f"Child process did not return valid JSON.\n"
            f"Exit code: {result.returncode}\n"
            f"Stdout: {result.stdout}\n"
            f"Stderr: {result.stderr}"
        )

    # Handle errors from the child
    if output["status"] == "error":
        pytest.fail(
            f"Child process encountered an error: "
            f"{output['error_type']}: {output['error_message']}\n"
            f"Stderr: {result.stderr}"
        )

    # Check import-time purity
    import_check = output["import_check"]
    if import_check["aiida_module"] is not None:
        chain_str = "\n".join(
            f"  {frame['file']}:{frame['line']}  {frame['source']}"
            for frame in import_check["blame_chain"]
        )
        pytest.fail(
            f"Operations import chain loaded AiiDA module "
            f"'{import_check['aiida_module']}'.\n"
            f"Import chain:\n{chain_str}"
        )

    # Check call-time purity
    call_check = output["call_check"]
    if call_check["aiida_module"] is not None:
        chain_str = "\n".join(
            f"  {frame['file']}:{frame['line']}  {frame['source']}"
            for frame in call_check["blame_chain"]
        )
        pytest.fail(
            f"Operation call loaded AiiDA module "
            f"'{call_check['aiida_module']}'.\n"
            f"Call chain:\n{chain_str}"
        )

    # Both checks passed
    assert output["status"] == "ok"
