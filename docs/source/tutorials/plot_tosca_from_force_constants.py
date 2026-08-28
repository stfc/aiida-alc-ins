"""TOSCA spectrum from CASTEP force constants
============================================

Run :class:`~aiida_pythonjob_ins.workflows.ToscaFromForceConstantsWorkChain` on
quartz force constants (a CASTEP ``.castep_bin``). The workflow reads the force
constants, samples phonon modes across the Brillouin zone, and delegates the
spectrum calculation to
:class:`~aiida_pythonjob_ins.workflows.ToscaFromModesWorkChain` -- which appears
in the provenance graph as a called sub-workflow.

.. note::

   **Quartz is an atypical TOSCA sample.** The calculation is legitimate --
   TOSCA samples a wide range of momentum transfer across many Brillouin zones,
   so the incoherent approximation works well even for a predominantly coherent
   scatterer like quartz -- but TOSCA is mostly used for hydrogenous molecular
   crystals, and quartz contains no hydrogen. Treat this page as a demonstration
   of the *method* and of composing the two workflows, not as a typical
   measurement. For a representative sample, see the ethanol example.
"""

# %%
# Set up AiiDA
# ------------
# A shared helper loads a temporary in-memory profile and a localhost Python code.

from _aiida_setup import example_data, get_python_code, show_provenance
from aiida import orm
from aiida.engine import run_get_node

code = get_python_code()

# %%
# Run the workflow
# ----------------
# Inputs for the delegated spectrum calculation live under the ``spectrum``
# namespace, keeping them clearly separate from this workflow's own
# force-constants and sampling inputs.
#
# .. note::
#
#    ``q_spacing`` here is deliberately coarse -- a 3x3x3 grid, far coarser than
#    the :doc:`density-of-states example <plot_dos>` uses on the same crystal --
#    purely to keep this page's build time down. ``abinslib``
#    combination-mode routine costs O(N^2) in the number of q-points (it
#    accumulates spectra by repeated addition, revalidating every previously
#    accumulated line each time), so a converged mesh would take tens of minutes
#    rather than seconds. The spectrum below is therefore under-sampled: the peak
#    *positions* are sound, but their relative intensities would shift on a finer
#    mesh.

from aiida.plugins import WorkflowFactory

# Load via WorkflowFactory (direct imports like
# `from aiida_pythonjob_ins.workflows import ToscaFromForceConstantsWorkChain`
# also work)
ToscaFromForceConstantsWorkChain = WorkflowFactory(
    "pythonjob_ins.tosca_from_force_constants"
)

results, node = run_get_node(
    ToscaFromForceConstantsWorkChain,
    castep_file=orm.SinglefileData(example_data("quartz.castep_bin")),
    q_spacing=orm.Float(0.5),  # MP-grid spacing (1/Angstrom); see the note above
    spectrum={
        "temperature": orm.Float(10.0),  # kelvin
        "energy_spacing": orm.Float(10.0),  # 1/cm
        "group_by": orm.List(list=["atom_symbol"]),
    },
    code=code,
)
print(f"WorkChain finished OK: {node.is_finished_ok}")

# %%
# Plot the spectrum
# -----------------
# The outputs are those of the delegated workflow, re-exposed as this
# workflow's own: the full ungrouped line set (``components``) and the grouped,
# broadened spectrum.

import matplotlib.pyplot as plt

spectrum = results["spectrum"]
_, energy, energy_unit = spectrum.get_x()
lines = spectrum.get_y()
intensity_unit = lines[0][2]  # shared by every line of the collection

fig, ax = plt.subplots()
for label, intensity, _ in lines:
    ax.plot(energy, intensity, label=label)
ax.set_xlabel(f"Energy transfer ({energy_unit})")
ax.set_ylabel(f"Intensity ({intensity_unit})")
ax.set_title("Quartz TOSCA spectrum (by element)")
ax.legend()
fig.tight_layout()

# %%
# Provenance
# ----------
# The graph shows the CASTEP read and mode-interpolation PythonJobs of this
# workflow, then the nested ``ToscaFromModesWorkChain`` doing the spectrum work.

show_provenance(node, title="TOSCA-from-force-constants workflow provenance")

# sphinx_gallery_thumbnail_number = 1
