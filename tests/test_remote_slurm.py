"""Integration tests running on a containerized SSH + Slurm computer."""

from __future__ import annotations

import time

import pytest
from aiida.engine import run_get_node
from aiida.orm import Float, SinglefileData, XyData
from aiida_pythonjob import PythonJob

from aiida_pythonjob_ins.pythonjobs import prepare_read_force_constants_inputs
from aiida_pythonjob_ins.workflows import DosWorkChain


@pytest.mark.containerized
def test_ssh_transport_raw(slurm_computer, tmp_path):
    """Test direct low-level SSH transport operations (echo, sinfo, sbatch, sftp)."""
    with slurm_computer.get_transport() as transport:
        # 1. Test basic command execution over SSH
        retval, stdout, stderr = transport.exec_command_wait("echo 'HELLO SLURM'")
        assert retval == 0, f"echo command failed: {stderr}"
        assert stdout.strip() == "HELLO SLURM"

        # 2. Test sinfo command over SSH
        retval, stdout, stderr = transport.exec_command_wait("sinfo -h -o %T")
        assert retval == 0, f"sinfo command failed: {stderr}"
        assert any(s in stdout for s in ("idle", "alloc")), f"state: {stdout}"

        # 3. Test SFTP file upload and directory creation
        transport.mkdir("/tmp/aiida_run/test_raw_job", ignore_existing=True)
        local_script = tmp_path / "run.sh"
        local_script.write_text(
            "#!/bin/bash\n"
            "echo 'BATCH JOB COMPLETED' > /tmp/aiida_run/test_raw_job/output.txt\n"
        )
        transport.putfile(
            str(local_script),
            "/tmp/aiida_run/test_raw_job/run.sh",
        )
        transport.exec_command_wait("chmod +x /tmp/aiida_run/test_raw_job/run.sh")

        # 4. Test sbatch job submission
        retval, stdout, stderr = transport.exec_command_wait(
            "sbatch /tmp/aiida_run/test_raw_job/run.sh",
            workdir="/tmp/aiida_run/test_raw_job",
        )
        assert retval == 0, f"sbatch command failed: {stderr}"

        # 5. Wait for job completion (up to 4s) and diagnose immediately if not done
        start_time = time.time()
        job_done = False
        while time.time() - start_time < 4.0:
            if transport.isfile("/tmp/aiida_run/test_raw_job/output.txt"):
                job_done = True
                break
            time.sleep(0.3)

        if not job_done:
            _, q_out, _ = transport.exec_command_wait("squeue")
            _, job_info, _ = transport.exec_command_wait(
                "scontrol show job 2>/dev/null || true",
            )
            _, daemon_logs, _ = transport.exec_command_wait(
                "tail -n 30 /var/log/slurm/slurmctld.log "
                "/var/log/slurm/slurmd.log 2>/dev/null || true",
            )
            msg = (
                f"Job did not write output within 4s.\n"
                f"--- squeue ---\n{q_out}\n"
                f"--- scontrol show job ---\n{job_info}\n"
                f"--- Slurm daemon logs ---\n{daemon_logs}"
            )
            raise AssertionError(msg)

        local_output = tmp_path / "output.txt"
        transport.getfile(
            "/tmp/aiida_run/test_raw_job/output.txt",
            str(local_output),
        )
        assert "BATCH JOB COMPLETED" in local_output.read_text()


@pytest.mark.containerized
def test_pythonjob_remote_slurm(slurm_python_code, quartz_castep_bin):
    """Run an individual PythonJob on remote Slurm computer over SSH."""
    castep_file = SinglefileData(quartz_castep_bin)
    inputs = prepare_read_force_constants_inputs(castep_file, code=slurm_python_code)
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
def test_dos_workchain_remote_slurm(slurm_python_code, quartz_castep_bin):
    """Run DosWorkChain on remote Slurm computer over SSH."""
    castep_file = SinglefileData(quartz_castep_bin)

    results, node = run_get_node(
        DosWorkChain,
        castep_file=castep_file,
        q_spacing=Float(0.5),  # coarse grid for speed
        energy_spacing=Float(2.0),
        code=slurm_python_code,
    )

    assert node.is_finished_ok, f"WorkChain failed: {node.exit_status}"
    dos = results["dos"]
    assert isinstance(dos, XyData)
    _, energy, _ = dos.get_x()
    ((_, values, _),) = dos.get_y()
    assert len(energy) == len(values)
    assert (values >= 0).all()
