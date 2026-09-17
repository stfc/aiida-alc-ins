"""AiiDA process wrappers around the atomic Euphonic operations.

We use ``aiida-pythonjob`` to run the plain functions in
:mod:`aiida_pythonjob_ins.operations` as AiiDA ``PythonJob`` processes.
``PythonJob`` runs through a ``Code`` on a ``Computer`` (localhost in tests, but
any configured machine in production), so the standard AiiDA Computer/Code hooks
apply. See https://github.com/aiidateam/aiida-pythonjob .

Code-environment note: aiida-pythonjob cloudpickles these module-level functions
*by reference* -- a tiny module+name string per job -- so the remote unpickles via
``from aiida_pythonjob_ins.operations import ...``. That module's import chain is
deliberately AiiDA-free, so loading the function on the remote does not import or
initialise aiida (no profile/config needed there). By-reference pickling is the
required execution strategy: scientific dependencies like Euphonic, NumPy, and
seekpath contain compiled C-extensions that cannot be pickled by value. See
"Remote Execution, Pickling, and register_pickle_by_value" in
docs/source/design_notes.rst.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aiida import orm
from aiida_pythonjob import prepare_pythonjob_inputs

from aiida_pythonjob_ins.operations import (
    band_path_qpoints,
    calculate_dispersion,
    calculate_dos,
    calculate_tosca_spectrum,
    interpolate_phonon_modes,
    interpolate_phonon_modes_on_grid,
    read_force_constants_from_castep,
    read_force_constants_from_phonopy,
)
from aiida_pythonjob_ins.serialization import (
    EUPHONIC_DESERIALIZERS,
    EUPHONIC_SERIALIZERS,
)

__all__ = [
    "band_path_qpoints",
    "calculate_dispersion",
    "calculate_dos",
    "calculate_tosca_spectrum",
    "interpolate_phonon_modes",
    "interpolate_phonon_modes_on_grid",
    "prepare_dispersion_inputs",
    "prepare_dos_inputs",
    "prepare_grid_interpolation_inputs",
    "prepare_interpolation_inputs",
    "prepare_read_force_constants_inputs",
    "prepare_read_phonopy_inputs",
    "prepare_tosca_spectrum_inputs",
    "read_force_constants_from_castep",
    "read_force_constants_from_phonopy",
]


def _staged_filename(file: str | orm.SinglefileData) -> str:
    """Basename under which ``upload_files`` stages a file in the working dir."""
    return file.filename if isinstance(file, orm.SinglefileData) else Path(file).name


def prepare_interpolation_inputs(
    force_constants: orm.Data,
    qpoints: orm.KpointsData,
    *,
    computer: str | orm.Computer = "localhost",
    code: orm.AbstractCode | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build inputs to run :func:`interpolate_phonon_modes` as a PythonJob.

    ``qpoints`` is a native ``KpointsData`` q-point specification, deserialized to
    a fractional-coordinate array before interpolation. The returned modes are
    serialized to a :class:`~aiida_pythonjob_ins.data.QpointPhononModesData`.

    Parameters
    ----------
    force_constants
        Force constants node.
    qpoints
        q-point path or mesh.
    computer, code
        Standard AiiDA execution targets.
    kwargs
        Extra arguments forwarded to
        :func:`~aiida_pythonjob.prepare_pythonjob_inputs`, such as
        ``metadata={"options": {"resources": {"num_cpus": 1}}}`` for
        scheduler options or ``upload_files``, ``parent_folder``, and
        ``process_label``.
    """
    return prepare_pythonjob_inputs(
        function=interpolate_phonon_modes,
        function_inputs={"force_constants": force_constants, "qpoints": qpoints},
        serializers=EUPHONIC_SERIALIZERS,
        deserializers=EUPHONIC_DESERIALIZERS,
        computer=computer,
        code=code,
        **kwargs,
    )


def prepare_read_force_constants_inputs(
    castep_file: str | orm.SinglefileData,
    *,
    computer: str | orm.Computer = "localhost",
    code: orm.AbstractCode | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build inputs to run :func:`read_force_constants_from_castep` as a PythonJob.

    The CASTEP file is staged into the job's working directory via ``upload_files``
    (mirroring how a real remote calculation stages its inputs); the function then
    reads it by basename and returns a ``ForceConstants`` serialized to a
    :class:`~aiida_pythonjob_ins.data.ForceConstantsData` node.

    Parameters
    ----------
    castep_file
        CASTEP .castep_bin or .check file path or SinglefileData node.
    computer, code
        Standard AiiDA execution targets.
    kwargs
        Extra arguments forwarded to
        :func:`~aiida_pythonjob.prepare_pythonjob_inputs`, such as
        ``metadata={"options": {"resources": {"num_cpus": 1}}}`` for
        scheduler options or ``upload_files``, ``parent_folder``, and
        ``process_label``.
    """
    filename = _staged_filename(castep_file)
    return prepare_pythonjob_inputs(
        function=read_force_constants_from_castep,
        function_inputs={"filename": filename},
        upload_files={"castep_file": castep_file},
        serializers=EUPHONIC_SERIALIZERS,
        deserializers=EUPHONIC_DESERIALIZERS,
        computer=computer,
        code=code,
        **kwargs,
    )


def prepare_read_phonopy_inputs(
    summary: str | orm.SinglefileData,
    force_constants: str | orm.SinglefileData,
    born: str | orm.SinglefileData | None = None,
    *,
    computer: str | orm.Computer = "localhost",
    code: orm.AbstractCode | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build inputs to run :func:`read_force_constants_from_phonopy` as a PythonJob.

    The Phonopy ``summary`` (``phonopy.yaml``), ``force_constants`` (e.g.
    ``FORCE_CONSTANTS``) and optional ``born`` (``BORN``) files are staged into the
    working directory via ``upload_files``; the function reads them by basename and
    returns a ``ForceConstants`` serialized to a ``ForceConstantsData`` node.

    Parameters
    ----------
    summary
        Path or SinglefileData for Phonopy summary YAML file.
    force_constants
        Path or SinglefileData for Phonopy force constants file.
    born
        Optional path or SinglefileData for Born effective charges.
    computer, code
        Standard AiiDA execution targets.
    kwargs
        Extra arguments forwarded to
        :func:`~aiida_pythonjob.prepare_pythonjob_inputs`, such as
        ``metadata={"options": {"resources": {"num_cpus": 1}}}`` for
        scheduler options or ``upload_files``, ``parent_folder``, and
        ``process_label``.
    """
    upload_files: dict[str, str | orm.SinglefileData] = {
        "summary": summary,
        "force_constants": force_constants,
    }
    function_inputs: dict[str, Any] = {
        "summary_name": _staged_filename(summary),
        "fc_name": _staged_filename(force_constants),
    }
    if born is not None:
        upload_files["born"] = born
        function_inputs["born_name"] = _staged_filename(born)

    return prepare_pythonjob_inputs(
        function=read_force_constants_from_phonopy,
        function_inputs=function_inputs,
        upload_files=upload_files,
        serializers=EUPHONIC_SERIALIZERS,
        deserializers=EUPHONIC_DESERIALIZERS,
        computer=computer,
        code=code,
        **kwargs,
    )


def prepare_dispersion_inputs(
    force_constants: orm.Data,
    q_spacing: float = 0.025,
    *,
    computer: str | orm.Computer = "localhost",
    code: orm.AbstractCode | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build the input dict to run :func:`calculate_dispersion` as a PythonJob.

    Parameters
    ----------
    force_constants
        A :class:`~aiida_pythonjob_ins.data.ForceConstantsData` node. It is
        deserialized to a Euphonic ``ForceConstants`` before the function runs.
    q_spacing
        Target q-point spacing in 1/Angstrom.
    computer, code
        Standard AiiDA execution targets. If ``code`` is ``None``,
        aiida-pythonjob resolves/creates a Python code on ``computer``.
    kwargs
        Extra arguments forwarded to
        :func:`~aiida_pythonjob.prepare_pythonjob_inputs`, such as
        ``metadata={"options": {"resources": {"num_cpus": 1}}}`` for
        scheduler options or ``upload_files``, ``parent_folder``, and
        ``process_label``.

    Returns
    -------
    dict
        Inputs to launch with ``aiida.engine.run``/``submit`` and
        ``aiida_pythonjob.PythonJob``.
    """
    return prepare_pythonjob_inputs(
        function=calculate_dispersion,
        function_inputs={"force_constants": force_constants, "q_spacing": q_spacing},
        # Teach PythonJob how to move our custom Data <-> Euphonic objects.
        serializers=EUPHONIC_SERIALIZERS,
        deserializers=EUPHONIC_DESERIALIZERS,
        computer=computer,
        code=code,
        **kwargs,
    )


def prepare_dos_inputs(
    force_constants: orm.Data,
    q_spacing: float = 0.1,
    energy_spacing: float = 1.0,
    *,
    computer: str | orm.Computer = "localhost",
    code: orm.AbstractCode | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build inputs to run :func:`calculate_dos` as a PythonJob.

    ``q_spacing`` is the target Monkhorst-Pack grid spacing (1/Angstrom) and
    ``energy_spacing`` the DOS bin width (meV). The returned euphonic ``Spectrum1D``
    is serialized to a native ``XyData``.

    Parameters
    ----------
    force_constants
        Force constants node.
    q_spacing
        Target Monkhorst-Pack grid spacing in 1/Angstrom.
    energy_spacing
        DOS energy bin width in meV.
    computer, code
        Standard AiiDA execution targets.
    kwargs
        Extra arguments forwarded to
        :func:`~aiida_pythonjob.prepare_pythonjob_inputs`, such as
        ``metadata={"options": {"resources": {"num_cpus": 1}}}`` for
        scheduler options or ``upload_files``, ``parent_folder``, and
        ``process_label``.
    """
    return prepare_pythonjob_inputs(
        function=calculate_dos,
        function_inputs={
            "force_constants": force_constants,
            "q_spacing": q_spacing,
            "energy_spacing": energy_spacing,
        },
        serializers=EUPHONIC_SERIALIZERS,
        deserializers=EUPHONIC_DESERIALIZERS,
        computer=computer,
        code=code,
        **kwargs,
    )


def prepare_grid_interpolation_inputs(
    force_constants: orm.Data,
    q_spacing: float = 0.1,
    *,
    computer: str | orm.Computer = "localhost",
    code: orm.AbstractCode | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build inputs to run :func:`interpolate_phonon_modes_on_grid` as a PythonJob.

    ``q_spacing`` is the target Monkhorst-Pack grid spacing (1/Angstrom), matching
    :func:`prepare_dos_inputs`'s convention. Used by
    ``ToscaFromForceConstantsWorkChain`` to obtain a powder-average q-point
    sampling for the TOSCA intensity calculation, as distinct from
    :func:`prepare_interpolation_inputs`'s caller-supplied path (used for a band
    structure).

    Parameters
    ----------
    force_constants
        Force constants node.
    q_spacing
        Target Monkhorst-Pack grid spacing in 1/Angstrom.
    computer, code
        Standard AiiDA execution targets.
    kwargs
        Extra arguments forwarded to
        :func:`~aiida_pythonjob.prepare_pythonjob_inputs`, such as
        ``metadata={"options": {"resources": {"num_cpus": 1}}}`` for
        scheduler options or ``upload_files``, ``parent_folder``, and
        ``process_label``.
    """
    return prepare_pythonjob_inputs(
        function=interpolate_phonon_modes_on_grid,
        function_inputs={"force_constants": force_constants, "q_spacing": q_spacing},
        serializers=EUPHONIC_SERIALIZERS,
        deserializers=EUPHONIC_DESERIALIZERS,
        computer=computer,
        code=code,
        **kwargs,
    )


def prepare_tosca_spectrum_inputs(
    modes: orm.Data,
    temperature: float = 10.0,
    energy_spacing: float = 10.0,
    energy_max: float = 4000.0,
    detector_angles: list[float] | None = None,
    final_energy: float = 32.0,
    energy_unit: str = "1/cm",
    *,
    computer: str | orm.Computer = "localhost",
    code: orm.AbstractCode | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build inputs to run :func:`calculate_tosca_spectrum` as a PythonJob.

    ``modes`` is a :class:`~aiida_pythonjob_ins.data.QpointPhononModesData` node,
    deserialized to a Euphonic ``QpointPhononModes`` before the function runs.
    The returned ``Spectrum1DCollection`` -- the full, ungrouped line set -- is
    serialized to a single native ``XyData`` with one y array per line (see
    :func:`aiida_pythonjob_ins.conversions.spectrum_collection_to_xydata`).

    ``detector_angles`` defaults to ``None`` here (rather than a mutable literal
    default) and is passed through unchanged; :func:`calculate_tosca_spectrum`
    supplies the actual default (TOSCA's two banks) so it is documented in one
    place.

    Parameters
    ----------
    modes
        Phonon modes node.
    temperature
        Sample temperature in kelvin.
    energy_spacing
        Energy bin width in ``energy_unit``.
    energy_max
        Maximum energy in ``energy_unit``.
    detector_angles
        Scattering angles in degrees.
    final_energy
        Final neutron energy in ``energy_unit``.
    energy_unit
        Energy unit string (e.g. '1/cm').
    computer, code
        Standard AiiDA execution targets.
    kwargs
        Extra arguments forwarded to
        :func:`~aiida_pythonjob.prepare_pythonjob_inputs`, such as
        ``metadata={"options": {"resources": {"num_cpus": 1}}}`` for
        scheduler options or ``upload_files``, ``parent_folder``, and
        ``process_label``.
    """
    return prepare_pythonjob_inputs(
        function=calculate_tosca_spectrum,
        function_inputs={
            "modes": modes,
            "temperature": temperature,
            "energy_spacing": energy_spacing,
            "energy_max": energy_max,
            "detector_angles": detector_angles,
            "final_energy": final_energy,
            "energy_unit": energy_unit,
        },
        serializers=EUPHONIC_SERIALIZERS,
        deserializers=EUPHONIC_DESERIALIZERS,
        computer=computer,
        code=code,
        **kwargs,
    )
