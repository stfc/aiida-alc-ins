"""Standalone WorkChain that resolves force constants from a source.

``ForceConstantsWorkChain`` is a launchable source-resolution unit: exactly one
of a CASTEP ``castep_file`` (``SinglefileData``), a Phonopy file set under a
``phonopy`` namespace, or a prepared ``node`` (``ForceConstantsData``) goes in,
and a ``force_constants`` output comes out. It dispatches no jobs and takes no
``Code`` or execution options -- remote or job-based sources are produced
upstream by the caller and passed as ``node``.

Consuming workflows (dispersion, DOS, TOSCA-from-force-constants) run it as a
sub-workflow, exposing its inputs under a ``force_constants`` namespace (see
:mod:`aiida_pythonjob_ins.workflows.base`). Keeping source resolution here means
the steps that turn an input into a ``ForceConstantsData`` can grow (new
formats, multi-step imports) without touching every consumer's outline, and
the unit can also be launched alone.

WorkChain reference:
https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/workflows/write.html
"""

from __future__ import annotations

import contextlib
import struct

import yaml
from aiida.engine import ExitCode, WorkChain, calcfunction, if_
from aiida.orm import SinglefileData

from aiida_pythonjob_ins.data import ForceConstantsData

#: Exceptions Euphonic's Phonopy reader raises for unreadable or invalid input,
#: as observed against malformed summaries, HDF5 and text files (see the
#: add-phonopy-force-constants-source design, Decision 4).
PHONOPY_READ_ERRORS = (OSError, ValueError, KeyError, TypeError, yaml.YAMLError)


@calcfunction
def read_castep_force_constants(
    castep_file: SinglefileData,
) -> ForceConstantsData | ExitCode:
    """Read a CASTEP ``SinglefileData`` into a :class:`ForceConstantsData` in-process.

    A calcfunction (not a dispatched PythonJob): the read takes about 0.1 s, so the
    ~2.8 s of job machinery it used to incur is unjustified. It records a
    ``CalcFunctionNode`` linking the file to the ``ForceConstantsData`` it
    produces, and it can be cached.

    An unreadable or invalid file returns an ``ExitCode(300, ...)`` rather than
    raising. All foreseeable Euphonic reader failures on truncated, corrupt, or
    non-phonon CASTEP inputs are caught per AiiDA's guidance to return an
    ``ExitCode`` for classifiable failures. ``RuntimeError`` is matched by
    message so that genuine internal bugs continue to propagate as Excepted
    processes.
    """
    try:
        with castep_file.as_path() as path:
            return ForceConstantsData.from_castep(path)
    except (EOFError, struct.error, OSError, ValueError) as exc:
        return ExitCode(300, f"Could not read CASTEP force constants: {exc}")
    except RuntimeError as exc:
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

    An in-process calcfunction, not a dispatched PythonJob, for the same reason as
    :func:`read_castep_force_constants`: the read is cheap. It records a
    ``CalcFunctionNode`` linking every supplied file (``summary``,
    ``force_constants``, ``born``) to the ``ForceConstantsData`` it produces, and
    it can be cached.

    Each file is read from its own temporary copy, under the file name it was
    stored with. Euphonic therefore sees the Phonopy file names, and the HDF5 or
    text format of ``force_constants`` is taken from that file name's suffix
    (``.hdf5``, ``.hd5`` and ``.h5`` select HDF5). ``force_constants`` may be
    omitted when the summary embeds force constants; ``born`` is optional.

    A foreseeable failure, such as a missing or malformed file, returns
    ``ExitCode(300, ...)`` rather than raising. Any other exception propagates, so
    that an internal bug surfaces as an Excepted process.
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
    """Resolve a ``ForceConstantsData`` from a CASTEP file, Phonopy files or a node.

    Exactly one of three sources is accepted:

    * a ``castep_file``, read in-process by the :func:`read_castep_force_constants`
      calcfunction;
    * a ``phonopy`` namespace (``summary``, optional ``force_constants`` and
      ``born``), read in-process by the :func:`read_phonopy_force_constants`
      calcfunction;
    * a ``node``, passed through directly with no calculation.

    Each file read records a ``CalcFunctionNode`` linking the supplied files to the
    output. The resolved force constants are exposed as the ``force_constants``
    output.

    It takes no ``Code`` or execution options: a ``node`` from a job-based source
    is produced upstream by the caller.

    Exit Codes:
        * 410 (ERROR_READ_FAILED): The force constants could not be read from a
          CASTEP or Phonopy file.
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
        """Read the supplied CASTEP file in-process and store the result.

        A failed read terminates the workflow with ``ERROR_READ_FAILED`` (410)
        before the ``finalize`` step, so no output is emitted.
        """
        result, node = read_castep_force_constants.run_get_node(self.inputs.castep_file)
        if not node.is_finished_ok:
            self.report(node.exit_message)
            return self.exit_codes.ERROR_READ_FAILED
        self.ctx.force_constants = result
        return None

    def read_phonopy(self) -> ExitCode | None:
        """Read the supplied Phonopy files in-process and store the result.

        A failed read terminates the workflow with ``ERROR_READ_FAILED`` (410)
        before the ``finalize`` step, so no output is emitted.
        """
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
