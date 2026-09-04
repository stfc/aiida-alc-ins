"""Shared pytest fixtures.

The official AiiDA pytest fixtures (``aiida_profile``, ``aiida_localhost``,
``aiida_code_installed``, ...) are provided by ``aiida.manage.tests.pytest_fixtures``.
Enabling them here gives every test a temporary, throwaway AiiDA profile so no
external services or persistent config are required.
https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/plugins.html#testing-a-plugin
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import tomllib
import venv
from pathlib import Path

import pytest

# -----------------------------------------------------------------------------
# Child environment builder for venv_code tests
# -----------------------------------------------------------------------------


class AiiDAFreeEnvBuilder(venv.EnvBuilder):
    """A venv.EnvBuilder that creates an AiiDA-free child environment.

    Creates a virtual environment, installs the project into it (non-editable),
    then uninstalls aiida-core and aiida-pythonjob to ensure the child
    interpreter has no AiiDA available.

    The child interpreter path is available via the `env_exe` attribute after
    creation.

    See design.md Decision 3 and Decision 4 for rationale.
    """

    def __init__(self, project_root: Path, find_links: list[str] | None = None) -> None:
        """Initialize the builder.

        Args:
            project_root: Path to the project root (for pip install .)
            find_links: Optional list of --find-links directories for wheels
        """
        super().__init__(with_pip=True, symlinks=True)
        self.project_root = project_root
        self.find_links = find_links or []
        self.env_exe: Path | None = None

    def post_setup(self, context: venv.SimpleNamespace) -> None:
        """Hook called after environment creation.

        Captures the child interpreter path and installs the project.
        """
        self.env_exe = Path(context.env_exe)


def get_find_links_from_pyproject(pyproject_path: Path) -> list[str]:
    """Read [tool.uv] find-links from pyproject.toml.

    Args:
        pyproject_path: Path to pyproject.toml

    Returns:
        List of find-links directories (empty if not present)
    """
    try:
        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)
        return data.get("tool", {}).get("uv", {}).get("find-links", [])
    except (FileNotFoundError, KeyError):
        return []


# Redirect AiiDA's configuration to an ephemeral, pytest-owned directory so the
# test session is hermetic: a developer's real, live ``~/.aiida`` (profiles,
# daemon, data) is never read or mutated, and tests run the same with or without
# an existing config.
#
# Why here (module top, before importing aiida): aiida-pythonjob builds its
# serializer registry at *import time*, calling ``get_config()``. With no existing
# config this raises MissingConfigurationError during pytest *collection* -- before
# any fixture can run -- as soon as a test module imports our package. AiiDA reads
# ``AIIDA_PATH`` to locate (and create) its ``.aiida`` config directory, so we set
# it to a fresh temp dir first, then create an empty config there. The
# ``aiida_profile`` fixtures still provide isolated, temporary profiles on top.
#
# ``TemporaryDirectory`` cleans itself up: explicitly via ``pytest_unconfigure``
# below, and as a safety net via its finalizer at interpreter exit. Keeping a
# module-level reference stops it being GC'd (and deleted) mid-session.
_AIIDA_CONFIG_TMPDIR = tempfile.TemporaryDirectory(
    prefix="aiida-test-config-", ignore_cleanup_errors=True
)
os.environ["AIIDA_PATH"] = _AIIDA_CONFIG_TMPDIR.name

from aiida.manage.configuration import get_config  # noqa: E402
from aiida.orm import Computer, InstalledCode  # noqa: E402
from tests.slurm_support import (  # noqa: E402
    SlurmContainer,
    detect_container_engine,
)

get_config(create=True)


def pytest_unconfigure(config):
    """Remove the ephemeral AiiDA config directory at the end of the session."""
    _AIIDA_CONFIG_TMPDIR.cleanup()


pytest_plugins = ["aiida.tools.pytest_fixtures"]

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def quartz_castep_bin() -> Path:
    """Path to the bundled quartz CASTEP force-constants file.

    Quartz is the canonical Euphonic example material; this ``.castep_bin``
    is copied from the Euphonic test suite.
    """
    return DATA_DIR / "quartz.castep_bin"


@pytest.fixture
def ethanol_modes_json() -> Path:
    """Path to the bundled ethanol phonon-modes JSON.

    A gamma-point ``QpointPhononModes`` dump vendored from ``abinslib``'s own
    test suite (see ``tests/data/README.md`` for provenance). Hydrogenous and
    molecular, unlike the quartz sample, so it is representative of TOSCA's
    usual application (see design.md's Decision 13).
    """
    return DATA_DIR / "ethanol_qpoint_phonon_modes.json"


@pytest.fixture
def phonopy_dir() -> Path:
    """Directory of the bundled NaCl Phonopy example (from the Euphonic suite)."""
    return DATA_DIR / "phonopy" / "NaCl_default"


@pytest.fixture
def phonopy_files(phonopy_dir) -> dict[str, str]:
    """Phonopy summary/force-constants/born file paths (as strings)."""
    return {
        "summary": str(phonopy_dir / "phonopy.yaml"),
        "force_constants": str(phonopy_dir / "FORCE_CONSTANTS"),
        "born": str(phonopy_dir / "BORN"),
    }


@pytest.fixture
def python_code(aiida_code_installed):
    """An AiiDA Code for running PythonJobs on localhost.

    Points at the *current* interpreter (``sys.executable``) so the job runs in
    this project's virtualenv, where euphonic and this package are installed.
    ``pythonjob.pythonjob`` is the calcjob plugin provided by aiida-pythonjob.
    """
    return aiida_code_installed(
        default_calc_job_plugin="pythonjob.pythonjob",
        filepath_executable=sys.executable,
    )


@pytest.fixture(scope="session")
def container_engine() -> str:
    """Detect podman/docker or skip containerized integration tests if unavailable."""
    engine = detect_container_engine()
    if not engine:
        pytest.skip("No working container engine (podman/docker) available")
    return engine


@pytest.fixture(scope="session")
def slurm_container(container_engine: str, tmp_path_factory: pytest.TempPathFactory):
    """Session-scoped Slurm container built from tests/container/Dockerfile."""
    key_dir = tmp_path_factory.mktemp("slurm_keys")
    project_root = Path(__file__).resolve().parent.parent
    container = SlurmContainer(
        engine=container_engine,
        project_root=project_root,
        key_dir=key_dir,
    )
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def slurm_computer(aiida_profile, slurm_container: SlurmContainer) -> Computer:
    """An AiiDA Computer configured for core.ssh + core.slurm on the container."""
    computer = Computer(
        label="slurm-container",
        hostname="127.0.0.1",
        transport_type="core.ssh",
        scheduler_type="core.slurm",
        workdir="/tmp/aiida_run",
    )
    computer.set_minimum_job_poll_interval(0.5)
    computer.set_default_mpiprocs_per_machine(1)
    computer.store()

    computer.configure(
        port=slurm_container.host_port,
        username="ubuntu",
        key_filename=str(slurm_container.ssh_key_file),
        load_system_host_keys=False,
        key_policy="AutoAddPolicy",
        safe_interval=0.0,
        use_login_shell=False,
        timeout=10,
    )
    return computer


@pytest.fixture(scope="session")
def slurm_python_code(slurm_computer: Computer) -> InstalledCode:
    """An AiiDA Code for running PythonJobs on the Slurm container."""
    code = InstalledCode(
        label="slurm-python",
        computer=slurm_computer,
        filepath_executable="/home/ubuntu/venv/bin/python",
        default_calc_job_plugin="pythonjob.pythonjob",
    )
    return code.store()


# -----------------------------------------------------------------------------
# Child environment fixture for venv_code tests
# -----------------------------------------------------------------------------


def _check_ensurepip_available() -> bool:
    """Check if ensurepip is available in the current Python.

    Returns:
        True if ensurepip is available, False otherwise
    """
    return importlib.util.find_spec("ensurepip") is not None


@pytest.fixture(scope="session")
def venv_child_environment(tmp_path_factory: pytest.TempPathFactory):
    """Session-scoped fixture providing an AiiDA-free child environment.

    Creates a virtual environment, installs the project into it (non-editable),
    then uninstalls aiida-core and aiida-pythonjob. This ensures the child
    interpreter has no AiiDA available, testing that PythonJob functions can
    run in a minimal environment with only the declared dependencies.

    Yields:
        Path to the child interpreter executable

    Raises:
        AssertionError: If AiiDA can still be imported after uninstallation

    Skips:
        If ensurepip is unavailable on the platform
    """
    # Check if ensurepip is available (Decision 9)
    if not _check_ensurepip_available():
        pytest.skip("ensurepip not available - cannot create child environment")

    # Get project root and find-links
    project_root = Path(__file__).resolve().parent.parent
    find_links = get_find_links_from_pyproject(project_root / "pyproject.toml")

    # Create venv directory under tmp_path_factory
    venv_dir = tmp_path_factory.mktemp("venv_child")

    # Create the environment using our custom builder (Decision 3)
    builder = AiiDAFreeEnvBuilder(project_root=project_root, find_links=find_links)
    builder.create(venv_dir)

    # The builder should have captured env_exe
    if builder.env_exe is None:
        msg = "env_exe not captured by AiiDAFreeEnvBuilder"
        raise RuntimeError(msg)

    child_python = builder.env_exe

    # Install the project non-editable (Decision 4)
    # Build the pip install command
    install_cmd = [str(child_python), "-m", "pip", "install", "--no-cache-dir"]

    # Add --find-links if present (Decision 8)
    for link_path in find_links:
        # Resolve relative to project root
        abs_link = project_root / link_path
        install_cmd.extend(["--find-links", str(abs_link)])

    # Install the project
    install_cmd.append(str(project_root))

    result = subprocess.run(
        install_cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = f"Failed to install project in child environment:\n{result.stderr}"
        raise RuntimeError(msg)

    # Uninstall aiida-core and aiida-pythonjob (Decision 4)
    uninstall_cmd = [
        str(child_python),
        "-m",
        "pip",
        "uninstall",
        "-y",
        "aiida-core",
        "aiida-pythonjob",
    ]
    result = subprocess.run(
        uninstall_cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    # Note: uninstall may fail if packages aren't installed, which is OK

    # Verify AiiDA cannot be imported (Decision 5)
    check_import_cmd = [
        str(child_python),
        "-c",
        "import aiida",
    ]
    result = subprocess.run(
        check_import_cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        msg = "AiiDA is still importable in child environment - uninstall failed"
        raise AssertionError(msg)

    # Verify aiida_pythonjob cannot be imported (Decision 5)
    check_import_cmd = [
        str(child_python),
        "-c",
        "import aiida_pythonjob",
    ]
    result = subprocess.run(
        check_import_cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        msg = (
            "aiida_pythonjob is still importable in child environment - "
            "uninstall failed"
        )
        raise AssertionError(msg)

    # Verify the venv has pyvenv.cfg (task 2.3 verification)
    pyvenv_cfg = venv_dir / "pyvenv.cfg"
    assert pyvenv_cfg.exists(), f"pyvenv.cfg not found at {pyvenv_cfg}"

    return child_python


@pytest.fixture
def remote_python_code(venv_child_environment: Path, aiida_code_installed):
    """An AiiDA Code for running PythonJobs in the AiiDA-free child environment.

    Points at the child interpreter from venv_child_environment, which has
    the project installed but no AiiDA packages. This tests that PythonJob
    functions can run in a minimal environment with only declared dependencies.

    Marked with venv_code so tests using it can be selected/deselected.
    """
    return aiida_code_installed(
        default_calc_job_plugin="pythonjob.pythonjob",
        filepath_executable=str(venv_child_environment),
    )


@pytest.fixture
def code(request):
    """Parametrized fixture that returns either python_code or remote_python_code.

    Used by tests that need to run against both the local interpreter and the
    AiiDA-free child interpreter.

    The request.param value should be either "python_code" or "remote_python_code".
    """
    if request.param == "python_code":
        return request.getfixturevalue("python_code")
    if request.param == "remote_python_code":
        return request.getfixturevalue("remote_python_code")
    msg = f"Unknown code fixture: {request.param}"
    raise ValueError(msg)
