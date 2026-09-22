# aiida-pythonjob-ins

### Caveat: agentic coding

This package is an experiment in the use of agentic coding to
accelerate development of research software infrastructure in the Ada
Lovelace Centre at STFC. It fits into a wider project and software
stack:

- **Python libraries** [Euphonic](https://euphonic.readthedocs.io)
  (phonon data import and Fourier interpolation);
  [abinslib](https://isisneutronmuon.github.io/abINS_lib/) (INS
  intensity calculations);
  [resins](https://pace-neutrons.github.io/resins/) (neutron
  instrument resolution functions).

- **AiiDA** This package wraps the Python stack into reproducible
  [AiiDA](https://www.aiida.net) workflows: each project is
  represented as a directed acyclic graph of calculation and data
  "nodes".

- **AiiDAlab** User-friendly graphical interfaces to AiiDA, intended
  for deployment to facilities users. These are being developed simultaneously,
  coordinated through https://github.com/stfc/alc-ux .

The inner (AiiDA plugin) layer is boilerplate-heavy and should be a
meticulous interface between our Python libraries and AiiDA,
presenting useful workflows for opinionated user-interface work in
AiiDAlab plugins. It was identified as a good candidate for agentic
development, which can refer to the AiiDA documentation, existing
plugins and the documentation/tests/implementation of the underlying
Python libraries. It is not supposed to include new scientific
decisions or give different results to other means of accessing those
libraries.

Initially this was an exploration of the
[`aiida-pythonjob`](https://github.com/aiidateam/aiida-pythonjob)
execution model; most AiiDA calculation plugins use command-line
interfaces, but the nature of *abinslib* and *resins* makes it awkward
to maintain and expose all their development through consistent CLIs.
Initial results were promising and so this has become the preferred implementation route.

After an ad-hoc "PLAN.md" start, this is being developed in
"spec-driven" style using various LLMs with
[openspec](https://openspec.dev/).  The behaviour this package
guarantees is specified in [`openspec/specs/`](./openspec/specs/), and
some more human-friendly reasoning behind the design is recorded in
[`docs/source/design_notes.rst`](./docs/source/design_notes.rst).


## Development setup

This project uses [`uv`](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync          # create .venv and install deps (+ dev group)
uv run pytest    # run the test suite (parallel by default)
```

Test execution is parallel by default, using `pytest-xdist` to run
across all available CPU cores. The containerized integration tests
are xdist-safe use a file lock to coordinate a shared container across
workers (see `conftest.py`).

To run tests sequentially (e.g. for debugging or clearer tracebacks):

```bash
uv run pytest -n 0
```

## What's implemented

- **Custom data types**: `ForceConstantsData`, `QpointPhononModesData`,
  `EuphonicCrystalData` (wrap Euphonic objects via their public JSON round-trip,
  stored in the node repository). `EuphonicCrystalData` bridges euphonic's
  `Crystal` to/from AiiDA's native `StructureData`.
- **Native AiiDA types**: the force constants' crystal is exposed as a
  `StructureData` (no ASE dependency), from which a `KpointsData` band path is
  built (also the *input* q-point specification for Fourier interpolation).
  Results map to `BandsData` (frequencies as bands), so `bands.show_mpl()` plots
  the phonon band structure with no AiiDALab dependency.
- **Atomic operations** (plain public-API functions): `band_path_qpoints`
  (seekpath; structure only), `read_force_constants_from_castep` and
  `interpolate_phonon_modes` (plus a `calculate_dispersion` convenience), and
  `calculate_tosca_spectrum` (inelastic-neutron-scattering intensities via
  `abinslib` + `resins`). The compute-heavy ops run as `aiida-pythonjob`
  `PythonJob`s.
- **Input formats**: read force constants from CASTEP (`.castep_bin`) or from
  Phonopy output (`phonopy.yaml` + `FORCE_CONSTANTS` [+ `BORN`]); read phonon
  modes from a Euphonic `QpointPhononModes` JSON dump.
- **Workflows** starting from force constants (each accepts a `castep_file` *or*
  a pre-built `force_constants` node, so they work equally from CASTEP or
  Phonopy input):
  - `DispersionWorkChain` chains a read PythonJob with three `calcfunction`s
    (extract structure, build q-point path, compose `BandsData`) and an
    interpolation PythonJob, with full provenance.
  - `DosWorkChain` computes a phonon density of states (Monkhorst-Pack sampling +
    adaptive broadening) as a native `XyData`.
  - `ToscaFromForceConstantsWorkChain` samples modes across the Brillouin zone
    and delegates to `ToscaFromModesWorkChain` below, re-exposing its outputs.
- **Workflows** starting from phonon modes:
  - `ToscaFromModesWorkChain` simulates the spectrum the TOSCA spectrometer
    would record: a PythonJob computes the full line set (per atom, quantum
    order and detector bank) as a native `XyData`, then `calcfunction`s group
    and resolution-broaden it. Splitting the steps this way means regrouping
    reuses the cached intensity calculation.

## Usage sketch

```python
import matplotlib
from aiida import load_profile, orm
from aiida.engine import run_get_node
from aiida.plugins import WorkflowFactory

load_profile()

# Load plugins via standard AiiDA factories (direct imports like
# `from aiida_pythonjob_ins.workflows import DispersionWorkChain` also work)
DispersionWorkChain = WorkflowFactory("pythonjob_ins.dispersion")

# A Python `Code` on some computer (here: interpreter with euphonic installed).
code = orm.load_code("python3@localhost")

results, node = run_get_node(
    DispersionWorkChain,
    castep_file=orm.SinglefileData("quartz.castep_bin"),
    q_spacing=orm.Float(0.025),
    code=code,
)

results["band_path"]  # KpointsData: q-point path + high-symmetry labels
results["band_structure"]  # BandsData: phonon band structure
results["phonon_modes"]  # QpointPhononModesData: frequencies + eigenvectors

# Plot with the native AiiDA/matplotlib tooling (no AiiDALab needed):
results["band_structure"].show_mpl()

# Or drop back to Euphonic objects when needed:
modes = results["phonon_modes"].get_modes()  # euphonic.QpointPhononModes
spectrum = modes.get_dispersion()  # euphonic.Spectrum1D
```

See `tests/` for runnable examples using the official AiiDA pytest fixtures.

## Documentation

Sphinx docs combine API reference (`sphinx-autoapi`) with a runnable tutorial
gallery (`sphinx-gallery`): each example executes a real AiiDA workflow, plots the
result, and visualises the provenance graph. Build them with:

```bash
uv run --group doc make -C docs html   # needs system Graphviz + procps
```

Output lands in `docs/build/html`. The gallery runs in a throwaway in-memory AiiDA
profile, so it never touches your real `~/.aiida`.

## Logging

The atomic operations emit progress messages through the standard `logging`
module under the `aiida_pythonjob_ins` logger namespace. As a library, this
package only *emits* logs; it never installs handlers or sets levels, so you
control verbosity from your application:

```python
import logging

# Show INFO-level messages from this package (basicConfig adds a stderr handler):
logging.basicConfig(level=logging.WARNING)
logging.getLogger("aiida_pythonjob_ins").setLevel(logging.INFO)
```

Use `logging.DEBUG` for more detail, or `logging.WARNING` (the effective default)
to silence progress messages. Because the package logger is separate from
AiiDA's own `aiida` logger, changing this level does not affect AiiDA's logging.

When an operation runs inside a `PythonJob` (a separate process), its stdout and
stderr are captured into the calculation's retrieved files. To have INFO logs
appear there, raise the level inside that process — e.g. via the code's
`prepend_text`, or AiiDA's logging configuration (`verdi config set`).

## References

- Euphonic — [docs](https://euphonic.readthedocs.io/),
  [PyPI](https://pypi.org/project/Euphonic/)
- `abinslib` — [docs](https://isisneutronmuon.github.io/abINS_lib/),
  [PyPI](https://pypi.org/project/abinslib/)
- `resins` — [docs](https://pace-neutrons.github.io/resins/),
  [PyPI](https://pypi.org/project/resins)
- [`aiida-pythonjob`](https://github.com/aiidateam/aiida-pythonjob) —
  [docs](https://aiida-pythonjob.readthedocs.io/)
- [Writing AiiDA plugins](https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/plugins.html)
  and [testing them](https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/plugins.html#testing-a-plugin)
- [AiiDA materials-science data types](https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/data_types.html#materials-science-data-types)
- Related in-house effort: [stfc/alc-ux](https://github.com/stfc/alc-ux)
