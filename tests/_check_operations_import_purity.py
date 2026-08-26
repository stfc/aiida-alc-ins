"""Check that the operations module import chain stays free of AiiDA.

This script is launched as a subprocess by test_import_purity.py. It runs in
a clean interpreter (AIIDA_PATH removed) with a recording meta_path finder
that observes imports without blocking. On completion, it reports results as
JSON on stdout.

Exit behavior:
- Exits 0 with JSON on stdout (status "ok" if no AiiDA imports detected)
- Exits 0 with JSON on stdout (status "error" if an exception occurred)
- Never exits non-zero (the parent interprets the JSON payload)
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path


class AiiDAImportRecorder:
    """Meta path finder that records AiiDA imports without blocking."""

    def __init__(self) -> None:
        self.first_hit_module: str | None = None
        self.blame_chain: list[dict[str, str | int]] = []

    def find_spec(self, name: str, path, target=None):
        # Match exactly 'aiida' or names starting with 'aiida.'
        # (not 'aiida_pythonjob_ins' or other packages with the same prefix)
        is_aiida = name == "aiida" or name.startswith("aiida.")
        if is_aiida and self.first_hit_module is None:
            self.first_hit_module = name
            # Capture the stack, dropping frames inside the import machinery
            # and inside AiiDA itself
            stack = traceback.extract_stack()
            self.blame_chain = [
                {
                    "file": frame.filename,
                    "line": frame.lineno,
                    "source": frame.line,
                }
                for frame in stack
                if not (
                    frame.filename.startswith("<")
                    or "importlib" in frame.filename
                    or "/aiida/" in frame.filename
                    or "\\aiida\\" in frame.filename
                )
            ]
        # Return None to let the import proceed (we're observing, not blocking)
        return


def report_and_exit(status: str, **kwargs) -> None:
    """Print JSON result and exit cleanly."""
    print(json.dumps({"status": status, **kwargs}))  # noqa: T201
    sys.exit(0)


def main() -> None:
    """Run the import purity check and report results as JSON."""
    # Insert recorder BEFORE importing anything else
    recorder = AiiDAImportRecorder()
    sys.meta_path.insert(0, recorder)

    # Now import the operations module
    try:
        import aiida_pythonjob_ins.operations as operations  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        report_and_exit("error", error_type=type(e).__name__, error_message=str(e))

    # Check after import
    import_hit = recorder.first_hit_module
    import_chain = recorder.blame_chain

    # Reset for the second phase (calling an operation)
    recorder.first_hit_module = None
    recorder.blame_chain = []

    # Call an operation: read force constants from castep file
    test_data_dir = Path(__file__).with_name("data")
    castep_file = test_data_dir / "quartz.castep_bin"
    try:
        operations.read_force_constants_from_castep(str(castep_file))
    except Exception as e:  # noqa: BLE001
        report_and_exit(
            "error",
            error_type=type(e).__name__,
            error_message=f"Operation failed: {e}",
        )

    # Check after operation call
    call_hit = recorder.first_hit_module
    call_chain = recorder.blame_chain

    # Report the results
    report_and_exit(
        "ok",
        import_check={"aiida_module": import_hit, "blame_chain": import_chain},
        call_check={"aiida_module": call_hit, "blame_chain": call_chain},
    )


if __name__ == "__main__":
    main()
