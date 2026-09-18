"""Shared pytest fixtures.

The official AiiDA pytest fixtures (``aiida_profile``, ``aiida_localhost``,
``aiida_code_installed``, ...) are provided by ``aiida.manage.tests.pytest_fixtures``.
Enabling them here gives every test a temporary, throwaway AiiDA profile so no
external services or persistent config are required.
https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/plugins.html#testing-a-plugin
"""

from __future__ import annotations

import importlib.util
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import venv
from pathlib import Path

import paramiko
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

import json  # noqa: E402

from aiida.manage.configuration import get_config  # noqa: E402
from aiida.orm import Computer, InstalledCode  # noqa: E402
from filelock import FileLock  # noqa: E402
from tests.container_support import (  # noqa: E402
    SSHContainer,
    SSHKeyPair,
    detect_container_engine,
)

get_config(create=True)


def pytest_unconfigure(config):
    """Remove the ephemeral AiiDA config directory at the end of the session."""
    _AIIDA_CONFIG_TMPDIR.cleanup()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Sort non-containerized tests first; containerized tests run last."""
    items.sort(key=lambda item: 1 if item.get_closest_marker("containerized") else 0)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Controller process stops the shared container once all workers finish."""
    if not hasattr(session.config, "workerinput"):
        tmp_factory = getattr(session.config, "_tmp_path_factory", None)
        if tmp_factory:
            shared_dir = tmp_factory.getbasetemp().parent
            info_file = shared_dir / "container_info.json"
            if info_file.is_file():
                try:
                    info = json.loads(info_file.read_text())
                    container_name = info.get("container_name")
                    if container_name:
                        for engine in ("podman", "docker"):
                            subprocess.run(
                                [engine, "rm", "-f", str(container_name)],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                check=False,
                            )
                except (OSError, json.JSONDecodeError):
                    logging.getLogger("tests.conftest").debug(
                        "Failed to parse container_info.json during teardown",
                        exc_info=True,
                    )
                finally:
                    info_file.unlink(missing_ok=True)


if not importlib.util.find_spec("xdist"):

    @pytest.fixture(scope="session")
    def worker_id() -> str:
        return "master"


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
def ssh_keypair(tmp_path_factory: pytest.TempPathFactory) -> SSHKeyPair:
    """Generate an ephemeral RSA SSH keypair for the test session."""
    key_dir = tmp_path_factory.mktemp("ssh")
    private_key = key_dir / "id_rsa"
    public_key = key_dir / "id_rsa.pub"

    key = paramiko.RSAKey.generate(2048)
    key.write_private_key_file(str(private_key))
    public_key.write_text(f"{key.get_name()} {key.get_base64()}\n")

    return SSHKeyPair(private_key=private_key, public_key=public_key)


ssh_key = ssh_keypair


@pytest.fixture(scope="session")
def remote_container_info(
    container_engine: str,
    ssh_keypair: SSHKeyPair,
    tmp_path_factory: pytest.TempPathFactory,
    worker_id: str,
) -> dict[str, str | int]:
    """Shared container connection info across xdist workers using FileLock."""
    project_root = Path(__file__).resolve().parent.parent

    if worker_id == "master":
        container = SSHContainer(
            engine=container_engine,
            project_root=project_root,
            keypair=ssh_keypair,
        )
        info = container.start()
        try:
            yield info
        finally:
            container.stop()
        return

    shared_dir = tmp_path_factory.getbasetemp().parent
    info_file = shared_dir / "container_info.json"
    lock_file = shared_dir / "container.lock"

    with FileLock(str(lock_file)):
        if info_file.is_file():
            info = json.loads(info_file.read_text())
        else:
            container = SSHContainer(
                engine=container_engine,
                project_root=project_root,
                keypair=ssh_keypair,
            )
            info = container.start()
            info_file.write_text(json.dumps(info))

    yield info


@pytest.fixture(scope="session")
def remote_computer(
    aiida_profile, remote_container_info: dict[str, str | int]
) -> Computer:
    """An AiiDA Computer configured for core.ssh + hyperqueue on the container."""
    computer = Computer(
        label="remote-container",
        hostname="127.0.0.1",
        transport_type="core.ssh",
        scheduler_type="hyperqueue",
        workdir="/tmp/aiida_run",
    )
    computer.set_minimum_job_poll_interval(0.5)
    computer.store()

    computer.configure(
        port=int(remote_container_info["host_port"]),
        username="ubuntu",
        key_filename=str(remote_container_info["ssh_key_file"]),
        load_system_host_keys=False,
        key_policy="AutoAddPolicy",
        safe_interval=0.0,
        use_login_shell=False,
        timeout=10,
    )
    return computer


@pytest.fixture(scope="session")
def remote_python_code(remote_computer: Computer) -> InstalledCode:
    """An AiiDA Code for running PythonJobs on the remote HyperQueue container."""
    code = InstalledCode(
        label="remote-python",
        computer=remote_computer,
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

    # Progressive enhancement: use uv when available on PATH for a much
    # faster install/uninstall cycle, falling back to plain pip otherwise
    # so the fixture stays tool-neutral (design.md Decision 1).
    uv_executable = shutil.which("uv")

    if uv_executable is not None:
        install_cmd = [
            uv_executable,
            "pip",
            "install",
            "--python",
            str(child_python),
            "--no-cache",
        ]
    else:
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
        msg = (
            "Failed to install project in child environment:\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )
        raise RuntimeError(msg)

    # Uninstall aiida-core and aiida-pythonjob (Decision 4)
    if uv_executable is not None:
        uninstall_cmd = [
            uv_executable,
            "pip",
            "uninstall",
            "--python",
            str(child_python),
            "aiida-core",
            "aiida-pythonjob",
        ]
    else:
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
def aiida_free_python_code(venv_child_environment: Path, aiida_code_installed):
    """An AiiDA Code for running PythonJobs in the AiiDA-free child environment.

    Points at the child interpreter from venv_child_environment, which has
    the project installed but no AiiDA packages. This tests that PythonJob
    functions can run in a minimal environment with only declared dependencies.
    """
    return aiida_code_installed(
        default_calc_job_plugin="pythonjob.pythonjob",
        filepath_executable=str(venv_child_environment),
    )


@pytest.fixture(params=["python_code", "aiida_free_python_code"])
def python_code_with_and_without_aiida(request):
    """Parametrized fixture providing both local and AiiDA-free PythonJob codes.

    Tests using this fixture run twice: once with the local interpreter
    (python_code) and once with the AiiDA-free child interpreter
    (aiida_free_python_code).
    """
    return request.getfixturevalue(request.param)
