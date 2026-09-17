"""Integration tests running on a containerized SSH + HyperQueue computer."""

from __future__ import annotations

import time

import pytest
from aiida.engine import run_get_node
from aiida.orm import Float, SinglefileData, XyData
from aiida_pythonjob import PythonJob

from aiida_pythonjob_ins.pythonjobs import prepare_read_force_constants_inputs
from aiida_pythonjob_ins.workflows import DosWorkChain


@pytest.mark.containerized
def test_ssh_transport_raw(remote_computer, tmp_path):
    """Test direct low-level SSH transport operations (echo, hq status, sftp)."""
    with remote_computer.get_transport() as transport:
        # 1. Test basic command execution over SSH
        retval, stdout, stderr = transport.exec_command_wait("echo 'HELLO SSH'")
        assert retval == 0, f"echo command failed: {stderr}"
        assert stdout.strip() == "HELLO SSH"

        # 2. Test HyperQueue server and worker status over SSH
        retval, stdout, stderr = transport.exec_command_wait(
            "hq server info && hq worker list"
        )
        assert retval == 0, f"hq server info check failed: {stderr}"
        assert "RUNNING" in stdout, f"HQ worker not running: {stdout}"

        # 3. Test SFTP file upload and directory creation
        transport.mkdir("/tmp/aiida_run/test_raw_job", ignore_existing=True)
        local_script = tmp_path / "run.sh"
        local_script.write_text(
            "#!/bin/bash\n"
            "echo 'SSH JOB COMPLETED' > /tmp/aiida_run/test_raw_job/output.txt\n"
        )
        transport.putfile(
            str(local_script),
            "/tmp/aiida_run/test_raw_job/run.sh",
        )
        transport.exec_command_wait("chmod +x /tmp/aiida_run/test_raw_job/run.sh")

        # 4. Execute script via HyperQueue submit
        retval, stdout, stderr = transport.exec_command_wait(
            "hq submit /tmp/aiida_run/test_raw_job/run.sh",
            workdir="/tmp/aiida_run/test_raw_job",
        )
        assert retval == 0, f"hq submit failed: {stderr}"

        # 5. Wait for job completion (up to 5s)
        start_time = time.time()
        job_done = False
        while time.time() - start_time < 5.0:
            if transport.isfile("/tmp/aiida_run/test_raw_job/output.txt"):
                job_done = True
                break
            time.sleep(0.3)

        if not job_done:
            _, jobs_out, _ = transport.exec_command_wait("hq jobs")
            _, worker_out, _ = transport.exec_command_wait("hq worker list")
            msg = (
                f"Job did not write output within 5s.\n"
                f"--- hq jobs ---\n{jobs_out}\n"
                f"--- hq worker list ---\n{worker_out}"
            )
            raise AssertionError(msg)

        local_output = tmp_path / "output.txt"
        transport.getfile(
            "/tmp/aiida_run/test_raw_job/output.txt",
            str(local_output),
        )
        assert "SSH JOB COMPLETED" in local_output.read_text()


@pytest.mark.containerized
def test_pythonjob_remote_ssh(remote_python_code, quartz_castep_bin):
    """Run an individual PythonJob on remote computer over SSH with HyperQueue."""
    castep_file = SinglefileData(quartz_castep_bin)
    inputs = prepare_read_force_constants_inputs(castep_file, code=remote_python_code)
    results, node = run_get_node(PythonJob, **inputs)

    if not node.is_finished_ok:
        details = ""
        retrieved = getattr(node.outputs, "retrieved", None)
        if retrieved:
            for fname in retrieved.base.repository.list_object_names():
                try:
                    content = retrieved.base.repository.get_object_content(fname)
                    details += f"\n--- {fname} ---\n{content[:2000]}"
                except (OSError, UnicodeDecodeError) as exc:
                    details += f"\n--- {fname} (binary/unreadable: {exc}) ---"
        msg = (
            f"PythonJob failed ({node.exit_status}): {node.exit_message}\n"
            f"Retrieved files:{details}"
        )
        raise AssertionError(msg)

    assert "result" in results


@pytest.mark.containerized
def test_dos_workchain_remote_ssh(remote_python_code, quartz_castep_bin):
    """Run DosWorkChain on remote computer over SSH with HyperQueue."""
    castep_file = SinglefileData(quartz_castep_bin)

    results, node = run_get_node(
        DosWorkChain,
        castep_file=castep_file,
        q_spacing=Float(0.5),  # coarse grid for speed
        energy_spacing=Float(2.0),
        code=remote_python_code,
    )

    assert node.is_finished_ok, f"WorkChain failed: {node.exit_status}"
    dos = results["dos"]
    assert isinstance(dos, XyData)
    _, energy, _ = dos.get_x()
    ((_, values, _),) = dos.get_y()
    assert len(energy) == len(values)
    assert (values >= 0).all()
