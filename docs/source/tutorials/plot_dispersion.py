"""Phonon band structure from CASTEP force constants
====================================================

Run :class:`~aiida_alc_ins.workflows.DispersionWorkChain` on quartz force
constants (a CASTEP ``.castep_bin``), plot the band structure, and visualise the
AiiDA provenance graph that produced it.
"""

# %%
# Set up AiiDA
# ------------
# A shared helper loads a temporary in-memory profile and a localhost Python code
# (see ``_aiida_setup.py``). Nothing here touches your real AiiDA configuration.

from _aiida_setup import example_data, get_python_code, show_provenance
from aiida import orm
from aiida.engine import run_get_node

code = get_python_code()

# %%
# Run the dispersion workflow
# ---------------------------
# The workflow reads the force constants (an in-process calcfunction), builds a
# seekpath q-point path, interpolates the phonon modes, and composes a band
# structure.

from aiida.plugins import WorkflowFactory

# Load via WorkflowFactory (direct imports like
# `from aiida_alc_ins.workflows import DispersionWorkChain` also work)
DispersionWorkChain = WorkflowFactory("alc_ins.dispersion")

results, node = run_get_node(
    DispersionWorkChain,
    force_constants={
        "castep_file": orm.SinglefileData(example_data("quartz.castep_bin"))
    },
    q_spacing=orm.Float(0.05),
    code=code,
)
print(f"WorkChain finished OK: {node.is_finished_ok}")
print(f"Outputs: {sorted(results)}")

# %%
# Plot the band structure
# -----------------------
# The output is a native AiiDA ``BandsData``; use its built-in matplotlib plotting.

bands = results["band_structure"]
bands.show_mpl()

# %%
# Provenance
# ----------
# Every step -- the interpolation PythonJob and the read/structure/path/bands
# calcfunctions -- is recorded. Here is the graph that produced the band
# structure.

show_provenance(node, title="Dispersion workflow provenance")
