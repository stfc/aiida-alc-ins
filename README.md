# aiida-alc-ins

An [AiiDA](https://www.aiida.net) plugin for lattice dynamics and inelastic neutron scattering (INS) simulations. It wraps Python libraries for phonon modelling and spectrum calculation ([Euphonic](https://euphonic.readthedocs.io/), [abinslib](https://isisneutronmuon.github.io/abINS_lib/), and [resins](https://pace-neutrons.github.io/resins/)) into reproducible workflows, using [aiida-pythonjob](https://github.com/aiidateam/aiida-pythonjob) to dispatch calculations directly from Python without command-line wrappers.

> ⚠️ **Status: Agentic Prototype**  
> This package is an experiment in use of agentic coding ("vibe coding") to accelerate research software infrastructure at the [STFC Ada Lovelace Centre](https://www.sc.stfc.ac.uk/programmes/ada-lovelace-centre-alc/). It has been developed rapidly with LLMs, as a thin layer around libraries providing the scientific capability. While changes are planned and tracked with [OpenSpec](https://openspec.dev/) and backed by automated integration tests, it has not undergone full line-by-line human review. Expect fast iteration and breaking changes before 1.0. **Do not use in production without reviewing the code.**

## Features

- **Input support**: Read force constants from CASTEP (`.castep_bin`) or Phonopy (`phonopy.yaml` + `FORCE_CONSTANTS` / `force_constants.hdf5`).
- **Lattice dynamics**: Compute phonon dispersions (`BandsData`) and density of states (`XyData`) with automatic band-path generation via [seeK-path](https://github.com/materialscloud-org/seekpath).
- **INS spectra**: Simulate inelastic neutron scattering on the TOSCA instrument (fundamentals and combination modes via `abinslib`, instrument resolution broadening via `resins`), with intensity decomposition grouped by element, atom, or quantum order.
- **Full provenance**: Workflows automatically record calculation steps, interpolation parameters, and intermediate modes in the AiiDA provenance graph.

## Installation

```bash
pip install aiida-alc-ins
```

## Quick Example: TOSCA Spectrum from Force Constants

```python
from aiida import load_profile, orm
from aiida.engine import run_get_node
from aiida.plugins import WorkflowFactory

load_profile()

ToscaFromForceConstantsWorkChain = WorkflowFactory(
    "pythonjob_ins.tosca_from_force_constants"
)
code = orm.load_code("python3@localhost")

results, node = run_get_node(
    ToscaFromForceConstantsWorkChain,
    force_constants={
        "castep_file": orm.SinglefileData("quartz.castep_bin"),
    },
    q_spacing=orm.Float(0.05),  # Monkhorst-Pack grid spacing (1/Å)
    spectrum={
        "temperature": orm.Float(10.0),  # Kelvin
        "energy_spacing": orm.Float(1.0),  # cm⁻¹
        "group_by": orm.List(["atom_symbol"]),
    },
    code=code,
)

# Spectrum is stored as native AiiDA XyData
spectrum_node = results["spectrum"]
_, energies, _ = spectrum_node.get_x()
for label, intensities, _ in spectrum_node.get_y():
    print(f"Computed {label} spectrum across {len(energies)} points")
```

## Documentation & Specs

- **Documentation**: [https://stfc.github.io/aiida-alc-ins/](https://stfc.github.io/aiida-alc-ins/)  
  Includes API reference and a tutorial gallery.
- **Specifications**: Changes and component behaviors are documented in [`openspec/specs/`](./openspec/specs/), with background reasoning in [`docs/source/design_notes.rst`](./docs/source/design_notes.rst).

## Development

Run the test suite with [`uv`](https://docs.astral.sh/uv/):

```bash
uv run pytest
```

`uv run` automatically creates `.venv` and installs dependencies. Integration tests run in parallel by default (`pytest-xdist`) using a shared, locked container fixture.
