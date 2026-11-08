"""Band structure and DOS from Phonopy input
============================================

Run :class:`~aiida_pythonjob_ins.workflows.DispersionWorkChain` and
:class:`~aiida_pythonjob_ins.workflows.DosWorkChain` on NaCl **Phonopy** output
(``phonopy_nofc_noborn.yaml`` + ``force_constants.hdf5`` + ``BORN_nacl``). The
files are passed straight to the workflows as their ``phonopy`` force-constants
source; nothing reads them in a separate step first.
"""

# %%
# Set up AiiDA
# ------------

from _aiida_setup import example_data, get_python_code, show_provenance
from aiida import orm
from aiida.engine import run_get_node

code = get_python_code()

# %%
# Band structure
# --------------
# The three Phonopy files are the ``phonopy`` source of the dispersion workflow.
# The workflow reads them in a ``read_phonopy_force_constants`` calculation, inside
# its ``ForceConstantsWorkChain`` sub-workflow.

from aiida.plugins import WorkflowFactory

# Load via WorkflowFactory (direct imports like
# `from aiida_pythonjob_ins.workflows import ...` also work)
DispersionWorkChain = WorkflowFactory("pythonjob_ins.dispersion")
DosWorkChain = WorkflowFactory("pythonjob_ins.dos")

phonopy_files = {
    "summary": orm.SinglefileData(
        example_data("phonopy", "NaCl_hdf5", "phonopy_nofc_noborn.yaml")
    ),
    "force_constants": orm.SinglefileData(
        example_data("phonopy", "NaCl_hdf5", "force_constants.hdf5")
    ),
    "born": orm.SinglefileData(example_data("phonopy", "NaCl_hdf5", "BORN_nacl")),
}

bands_results, bands_node = run_get_node(
    DispersionWorkChain,
    force_constants={"phonopy": phonopy_files},
    q_spacing=orm.Float(0.1),
    code=code,
)
bands_results["band_structure"].show_mpl()

# %%
# Density of states
# -----------------
# ``DispersionWorkChain`` does not output its force constants. The DOS takes them
# from the ``ForceConstantsWorkChain`` child of the band-structure run instead. The
# files are then not read a second time, and the DOS shares the same provenance.

fc_child = next(
    child
    for child in bands_node.called
    if child.process_label == "ForceConstantsWorkChain"
)

dos_results, _ = run_get_node(
    DosWorkChain,
    force_constants={"node": fc_child.outputs.force_constants},
    q_spacing=orm.Float(0.2),
    energy_spacing=orm.Float(1.0),
    code=code,
)

import matplotlib.pyplot as plt

dos = dos_results["dos"]
_, energy, energy_unit = dos.get_x()
((_, density, dos_unit),) = dos.get_y()

fig, ax = plt.subplots()
ax.plot(energy, density)
ax.set_xlabel(f"Energy ({energy_unit})")
ax.set_ylabel(f"Density of states ({dos_unit})")
ax.set_title("NaCl phonon DOS (from Phonopy)")
fig.tight_layout()

# %%
# Provenance
# ----------
# The graph traces the band structure back through the dispersion workflow and its
# ``ForceConstantsWorkChain`` to the ``read_phonopy_force_constants`` calculation,
# which links the three Phonopy files -- the full history in one picture.

show_provenance(bands_node, title="Phonopy -> dispersion provenance")
