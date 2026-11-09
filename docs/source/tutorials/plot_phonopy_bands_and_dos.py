"""Band structure and DOS from Phonopy input
============================================

Run :class:`~aiida_pythonjob_ins.workflows.DispersionWorkChain` and
:class:`~aiida_pythonjob_ins.workflows.DosWorkChain` on NaCl **Phonopy** output
(``phonopy_nofc_noborn.yaml`` + ``force_constants.hdf5`` + ``BORN_nacl``). The
files are passed straight to each workflow as its ``phonopy`` force-constants
source; nothing reads them in a separate step first. The last section shows how
AiiDA caching lets the second workflow reuse the first one's read.
"""

# %%
# Set up AiiDA
# ------------

from _aiida_setup import example_data, get_python_code, show_provenance
from aiida import orm
from aiida.engine import run_get_node

code = get_python_code()

# %%
# Load the workflows
# ------------------
# The three Phonopy files are the ``phonopy`` source of each workflow. Each reads
# them inside its ``ForceConstantsWorkChain`` sub-workflow.

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

# %%
# Enable caching
# --------------
# Caching is switched on for the Phonopy read so that the second workflow below
# can reuse the first one's result. It is an optional detail, explained at the end.

from aiida.manage.configuration import get_config

READ_PHONOPY_PROCESS_TYPE = (
    "aiida_pythonjob_ins.workflows.force_constants.read_phonopy_force_constants"
)
get_config().set_option("caching.enabled_for", [READ_PHONOPY_PROCESS_TYPE])

# %%
# Band structure
# --------------
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
# The DOS workflow is given the same files.

dos_results, dos_node = run_get_node(
    DosWorkChain,
    force_constants={"phonopy": phonopy_files},
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

# %%
# Avoiding the repeated read
# --------------------------
# Both workflows were given the same Phonopy files, and each records its own
# ``read_phonopy_force_constants`` calculation. Because caching was enabled at the
# start, the DOS run did not read the files again: AiiDA recognised the same file
# contents and reused the result of the first read.
#
# So to run several workflows on one Phonopy file set, pass the same files each
# time. Caching is off by default in AiiDA; the `AiiDA caching documentation
# <https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/provenance/caching.html>`_
# explains how to enable it permanently for a profile.

# %%
# The DOS run's read is marked as created from the cache. Asserting this means a
# silent loss of cacheability fails the documentation build instead of passing
# unnoticed.

dos_reads = [
    process
    for process in dos_node.called_descendants
    if process.process_label == "read_phonopy_force_constants"
]
reused = all(read.base.caching.is_created_from_cache for read in dos_reads)
print(f"Phonopy read taken from the cache: {reused}")
assert dos_reads
assert reused, "expected the DOS run to reuse the cached Phonopy read"

# %%
# Alternative: reuse the force-constants node directly
# ----------------------------------------------------
# The force constants can also be taken from the first run and passed to another
# workflow as its ``node`` source, which needs no caching. ``DispersionWorkChain``
# does not output them, so they are found as the output of its
# ``ForceConstantsWorkChain`` child. This suits a node you want to hold on to
# explicitly, such as one built by other means.

fc_child = next(
    child
    for child in bands_node.called
    if child.process_label == "ForceConstantsWorkChain"
)
force_constants_node = fc_child.outputs.force_constants

# The node would be passed as
# ``DosWorkChain, force_constants={"node": force_constants_node}``.
print(f"Force constants node: {force_constants_node.uuid}")
