"""Resolve force constants from a CASTEP file, Phonopy files or a prepared node.

See :class:`ForceConstantsWorkChain`. Consuming workflows expose its inputs under
``force_constants`` (see :mod:`aiida_alc_ins.workflows.base`).

WorkChain reference:
https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/workflows/write.html
"""

from __future__ import annotations

import contextlib
import struct

import yaml
from aiida.engine import ExitCode, WorkChain, calcfunction, if_
from aiida.orm import SinglefileData

from aiida_alc_ins.data import ForceConstantsData

#: Exceptions Euphonic's Phonopy reader raises for unreadable or invalid input
#: (malformed summary, HDF5 or text file). Anything else is a bug and propagates.
PHONOPY_READ_ERRORS = (OSError, ValueError, KeyError, TypeError, yaml.YAMLError)


@calcfunction
def read_castep_force_constants(
    castep_file: SinglefileData,
) -> ForceConstantsData | ExitCode:
    """Read a CASTEP ``SinglefileData`` into a :class:`ForceConstantsData`.

    An unreadable or invalid file returns ``ExitCode(300)``. Other exceptions
    propagate.
    """
    try:
        with castep_file.as_path() as path:
            return ForceConstantsData.from_castep(path)
    except (EOFError, struct.error, OSError, ValueError) as exc:
        return ExitCode(300, f"Could not read CASTEP force constants: {exc}")
    except RuntimeError as exc:
        # Euphonic signals bad CASTEP input with a bare RuntimeError, so match by
        # message; any other RuntimeError is a bug and must propagate.
        msg = str(exc)
        if "Force constants matrix could not be found" in msg or "Invalid file" in msg:
            return ExitCode(300, f"Could not read CASTEP force constants: {exc}")
        raise


@calcfunction
def read_phonopy_force_constants(
    summary: SinglefileData,
    force_constants: SinglefileData | None = None,
    born: SinglefileData | None = None,
) -> ForceConstantsData | ExitCode:
    """Read Phonopy ``SinglefileData`` files into a :class:`ForceConstantsData`.

    Each file is read from a temporary copy under its stored name, so Euphonic
    infers the force-constants format from the suffix. A missing or malformed
    file returns ``ExitCode(300)``. Other exceptions propagate.
    """
    try:
        with contextlib.ExitStack() as stack:
            summary_path = stack.enter_context(summary.as_path())
            kwargs = {"path": summary_path.parent, "summary_name": summary_path.name}
            if force_constants is not None:
                kwargs["fc_name"] = str(stack.enter_context(force_constants.as_path()))
            if born is not None:
                kwargs["born_name"] = str(stack.enter_context(born.as_path()))
            return ForceConstantsData.from_phonopy(**kwargs)
    except PHONOPY_READ_ERRORS as exc:
        return ExitCode(300, f"Could not read Phonopy force constants: {exc}")


class ForceConstantsWorkChain(WorkChain):
    """Resolve a ``ForceConstantsData`` from ``castep_file``, ``phonopy`` or ``node``.

    Exactly one source is accepted. Files are read in-process by a calcfunction,
    which links them to the output in provenance; a ``node`` passes through
    unchanged. No ``Code`` is needed: job-based sources are produced upstream and
    passed as ``node``.

    Exit Codes:
        * 410 (ERROR_READ_FAILED): A CASTEP or Phonopy file could not be read.
    """

    @classmethod
    def define(cls, spec) -> None:
        super().define(spec)
        spec.input(
            "castep_file",
            valid_type=SinglefileData,
            required=False,
            help=(
                "CASTEP .castep_bin/.check file, read in-process by the "
                "``read_castep_force_constants`` calcfunction."
            ),
        )
        spec.input_namespace(
            "phonopy",
            required=False,
            help=(
                "Phonopy output files; read in-process by "
                "`read_phonopy_force_constants`."
            ),
        )
        spec.input(
            "phonopy.summary",
            valid_type=SinglefileData,
            help=(
                "Phonopy summary file (`phonopy.yaml`). Required when `phonopy` is "
                "used."
            ),
        )
        spec.input(
            "phonopy.force_constants",
            valid_type=SinglefileData,
            required=False,
            help=(
                "Force-constants file: HDF5 if the file name ends in .hdf5/.hd5/.h5, "
                "otherwise Phonopy text format (FORCE_CONSTANTS). Omit if the summary "
                "already contains force constants."
            ),
        )
        spec.input(
            "phonopy.born",
            valid_type=SinglefileData,
            required=False,
            help=(
                "Born-charges file (BORN). Ignored if the summary already holds "
                "Born data."
            ),
        )
        spec.input(
            "node",
            valid_type=ForceConstantsData,
            required=False,
            help=(
                "A prepared `ForceConstantsData`, built by any means; passed through "
                "unchanged."
            ),
        )
        spec.inputs.validator = cls._validate_source
        spec.outline(
            if_(cls.has_castep_file)(cls.read_castep_file)
            .elif_(cls.has_phonopy)(cls.read_phonopy)
            .else_(cls.use_node),
            cls.finalize,
        )
        spec.output(
            "force_constants",
            valid_type=ForceConstantsData,
            help="The resolved force constants (read from a file or passed through).",
        )
        spec.exit_code(
            410,
            "ERROR_READ_FAILED",
            message="The force constants could not be read.",
        )

    @staticmethod
    def _validate_source(inputs, _port) -> str | None:
        """Require exactly one of ``castep_file`` / ``phonopy`` / ``node``.

        The ``phonopy`` key is always present in ``inputs``, as an empty mapping when
        the caller omitted it, so its presence is tested by truthiness.
        """
        given = [
            "castep_file" in inputs,
            bool(inputs.get("phonopy")),
            "node" in inputs,
        ]
        if sum(given) != 1:
            return "Provide exactly one of `castep_file`, `phonopy` or `node`."
        return None

    def has_castep_file(self) -> bool:
        """Return whether a CASTEP file was supplied as the source."""
        return "castep_file" in self.inputs

    def has_phonopy(self) -> bool:
        """Return whether a Phonopy file set was supplied as the source."""
        return bool(self.inputs.get("phonopy"))

    def read_castep_file(self) -> ExitCode | None:
        """Read the CASTEP file; fail with ``ERROR_READ_FAILED``."""
        result, node = read_castep_force_constants.run_get_node(self.inputs.castep_file)
        if not node.is_finished_ok:
            self.report(node.exit_message)
            return self.exit_codes.ERROR_READ_FAILED
        self.ctx.force_constants = result
        return None

    def read_phonopy(self) -> ExitCode | None:
        """Read the Phonopy files; fail with ``ERROR_READ_FAILED``."""
        result, node = read_phonopy_force_constants.run_get_node(**self.inputs.phonopy)
        if not node.is_finished_ok:
            self.report(node.exit_message)
            return self.exit_codes.ERROR_READ_FAILED
        self.ctx.force_constants = result
        return None

    def use_node(self):
        """Pass the supplied force-constants node through directly."""
        self.ctx.force_constants = self.inputs.node

    def finalize(self) -> None:
        """Expose the resolved force constants as the workflow output."""
        self.out("force_constants", self.ctx.force_constants)
