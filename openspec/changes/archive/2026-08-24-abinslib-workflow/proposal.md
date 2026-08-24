## Why

The plugin currently stops at lattice dynamics: it turns force constants into a
band structure or a density of states. Neither is what an ISIS user actually
measures. The scientific point of an *inelastic-neutron-scattering* plugin is the
simulated spectrum an instrument would record, and demonstrating that end-to-end
pipeline under AiiDA provenance is the exemplar this proof-of-concept was built
to provide.

The pieces now exist as libraries: `abinslib` computes almost-isotropic
incoherent intensities (fundamentals plus Mantid/AbINS-style combination modes)
from Euphonic `QpointPhononModes`, and `resins` supplies the instrument
resolution functions. Wiring them behind a WorkChain exercises parts of the
architecture that the phonon-only workflows never touch — notably a multi-column
`Spectrum1DCollection` result whose per-column metadata must survive the trip
into an AiiDA node.

This change deliberately targets **one instrument, TOSCA**, following the
`abinslib` reference example. TOSCA's indirect geometry — two detector banks at
fixed angles with an analyser-fixed final energy — pins down the kinematics
completely, which keeps the demonstrator concrete and testable. A general
multi-instrument abstraction is a harder design problem and is deferred; naming
the workflow after the instrument it actually models avoids promising generality
that is not there.

The demonstrator should use a molecular crystal rather than the existing quartz
sample. This is a matter of audience, not of validity: because TOSCA samples a
wide range of momentum transfer across many Brillouin zones, the incoherent
approximation works well even for predominantly coherent scatterers such as
quartz. The reason to prefer an organic crystal is that hydrogenous molecular
samples are what TOSCA is mostly used for, so such an example is more
recognisable to its users and far easier to compare against the published
literature. `abinslib`'s own ethanol modes serve exactly that role in its test
suite.

## What Changes

- **New sample data: an ethanol phonon calculation.** `abinslib`'s
  `ethanol_qpoint_phonon_modes.json` (a ~310 kB Euphonic `QpointPhononModes`
  dump, nine atoms, GPL-3-licensed like this project) is bundled alongside the
  existing quartz file, so the tutorial stays offline and hydrogen-rich.
- **No new code for loading modes.** `QpointPhononModesData.from_json_file` is
  already inherited from `EuphonicJSONData` and already specified, so the ethanol
  dump becomes a node in one line. The workflow that consumes modes requires that
  *node*, not a file: keeping the core narrow is what lets file-ingest chains be
  composed around it later, and Euphonic's own JSON needs no conversion step
  because the node stores it byte-for-byte. Reading modes from formats that do
  need converting — a CASTEP `.phonon` file, a Phonopy `band.yaml` set — is a
  natural follow-up along the same lines as the existing force-constants readers.
- **New TOSCA operations** (`abinslib` + `resins`, AiiDA-free, in the
  `operations.py` layer): thermal displacements from modes, indirect-geometry
  kinematics (`Q²` per mode and per bin) for a given detector angle and final
  energy, fundamental and combination spectra, and TOSCA resolution broadening
  via `resins`.
- **Two composed WorkChains** in `workflows/tosca.py`, rather than one chain that
  accepts either kind of input. Where a workflow's *required parameters* differ
  by input type, a single flat process spec cannot express that honestly —
  `q_spacing` is mandatory for force constants and meaningless for precomputed
  modes. Splitting follows AiiDA's own composition idiom (`PwBandsWorkChain`
  exposing `PwBaseWorkChain` under a namespace):

  - **`ToscaFromModesWorkChain`**, entry point `pythonjob_ins.tosca_from_modes`.
    Takes `QpointPhononModesData` plus the instrument and sample parameters, and
    is independently runnable — this is the ethanol case.
  - **`ToscaFromForceConstantsWorkChain`**, entry point
    `pythonjob_ins.tosca_from_force_constants`. Takes the existing
    force-constants sources plus `q_spacing`, interpolates modes, and delegates
    to the modes chain through `expose_inputs`/`expose_outputs`.

  Both chains produce a TOSCA spectrum, so they are named for the input that
  distinguishes them, following Euphonic's own `from_castep`/`from_modes`
  convention. Neither name is privileged: a user scanning the installed workflows
  can see at once which chain matches the data they hold.

  `ToscaFromForceConstantsWorkChain` **inherits** `ForceConstantsWorkChain` — it
  genuinely is a force-constants-sourced chain, and so reuses the existing source
  validator — while **composing** `ToscaFromModesWorkChain`. Inheritance answers
  "where do the force constants come from"; composition answers "what is done
  with the modes". Both existing conventions in the codebase stay intact.

  Note that the existing `castep_file | force_constants` either/or is *not* the
  pattern being avoided here: both sources yield the same object and neither
  changes the required parameter set. The rule the design should record is that
  an either/or port is acceptable only when the alternatives are interchangeable
  sources of one object, not when they change what else must be supplied.

- **`ToscaFromModesWorkChain` runs in two separate provenance steps**:
  1. a heavy PythonJob producing the **full, ungrouped line set** — every
     atom × quantum-order component — stored as an `XyData`;
  2. a cheap `calcfunction` that **groups and sums** that line set according to
     user-supplied metadata keys.

  Splitting them this way is the point of the design: with caching enabled, a
  user can re-run grouping by `quantum_order` instead of `atom_symbol` and pay
  only for the second step, while the expensive intensity calculation is reused
  from the graph. Because the split lives in the modes chain, this holds whether
  it is run directly or nested inside the force-constants chain.
- **Grouping is a workflow input.** `ToscaFromModesWorkChain` takes a list of
  metadata keys to group by (for example `["atom_symbol"]`, `["quantum_order"]`,
  or both), defaulting to a total spectrum, and outputs both the full line set and
  the grouped result. `ToscaFromForceConstantsWorkChain` re-exposes both.
- **New conversions between `Spectrum1DCollection` and `XyData`.** The two types
  are near-equivalent — a shared x axis with several y columns — except that
  AiiDA arrays carry only a name and a unit string, while Euphonic columns carry
  a metadata dict (`atom_symbol`, `quantum_order`, …). Three functions are added:
  - forward: collection → `XyData`, serialising each column's metadata into its
    y-array name so grouping information is not lost;
  - reverse: `XyData` → collection, recovering the metadata so Euphonic's own
    `group_by()`/`select()`/`sum()` can be used on data read back from the graph
    — this is what makes the grouping step possible;
  - labelling: a companion that turns a column's metadata into a concise,
    human-readable legend label for plotting, so consumers do not have to parse
    the encoded array name themselves.

  This trio is instrument-agnostic and will serve any later instrument.
- **New serializer registration** so a PythonJob returning a
  `Spectrum1DCollection` is stored as `XyData` automatically, mirroring the
  existing `Spectrum1D` handling.
- **New dependencies**, both pre-1.0 and explicitly unstable, so both are pinned
  narrowly: `abinslib==0.1.*` (alpha; the API is expected to change) and
  `resins~=0.1.0` (its own README advises pinning; `abinslib` 0.1 already
  requires `resins==0.1.0` exactly, so the resolver enforces this regardless).
- **Two new gallery tutorials**, one per chain:
  - `ToscaFromModesWorkChain` on the bundled ethanol modes, plotting the spectrum
    grouped by quantum order and then by element — the second plot re-using the
    cached heavy step to make the caching argument visible — plus the provenance
    graph;
  - `ToscaFromForceConstantsWorkChain`, showing the interpolation step and the
    nested sub-workchain in the provenance graph.

  The force-constants example initially uses the bundled quartz data. The result
  is a legitimate calculation — the incoherent approximation is sound for quartz
  at TOSCA's momentum transfers — but it is an **atypical** TOSCA measurement and
  therefore a less illustrative example. Swapping it for a molecular-crystal
  force-constants dataset is **deferred to a follow-up change**: no suitable
  bundled dataset was to hand, and finding one that is redistributable under a
  compatible licence, small enough to vendor and citable to a pinned upstream
  source is a self-contained piece of work. The page states its own
  unrepresentativeness in the meantime, which is what the `documentation`
  capability requires of it, so nothing here is left unsatisfied.
- **New tests** covering the operations, the collection ↔ `XyData` round trip,
  the labelling helper, and both chains including the grouping step and the
  nesting.

No existing behaviour is removed or altered; this change is additive.

## Capabilities

### New Capabilities

- `tosca-spectra`: AiiDA-free operations that turn phonon modes into a simulated
  TOSCA inelastic-neutron-scattering spectrum — thermal displacements and
  Debye-Waller factors, the indirect-geometry kinematic constraint for a chosen
  detector bank, fundamental and combination-mode intensities, and TOSCA's
  energy-dependent resolution broadening.

### Modified Capabilities

- `pythonjob-execution`: its requirement enumerates the input builders provided
  for launching operations as jobs, so adding one for the TOSCA intensity
  calculation modifies it.
- `phonon-workflows`: gains requirements for a TOSCA spectrum workflow that runs
  from precomputed modes and outputs an instrument-resolved spectrum — including
  that the ungrouped line set is committed to the graph before grouping, so that
  regrouping is cacheable — and for a force-constants-sourced workflow that
  composes it. The existing "exactly one source of force constants" requirement
  is unchanged: `ToscaFromForceConstantsWorkChain` inherits it as-is.
- `aiida-native-conversions`: the existing "Spectra convert to a native XyData"
  requirement extends from a single `Spectrum1D` to a multi-column
  `Spectrum1DCollection`, and gains metadata preservation, reverse conversion,
  and metadata-derived plot labels.
- `plugin-packaging`: the entry-point requirement enumerates the registered set,
  so adding `pythonjob_ins.tosca_from_modes` and
  `pythonjob_ins.tosca_from_force_constants` modifies it; the
  dependency-rationale requirement covers the two new pinned dependencies.
- `documentation`: the example-gallery requirement enumerates which examples must
  exist, so adding the two TOSCA tutorials modifies it.

## Non-goals

- **Not a general INS instrument framework.** The workflows model TOSCA and are
  named for it. Other instruments — and any multi-instrument abstraction that
  generalises over geometry, banks and resolution models — are deliberately left
  to later changes, once there is more than one concrete case to generalise from.
- **No high-level either/or wrapper chain.** A third chain dispatching on whether
  modes or force constants were supplied is not built here: for a demonstrator,
  `ToscaFromForceConstantsWorkChain` already serves anyone holding force
  constants. The two-chain
  split is chosen so that such a wrapper *remains possible* — AiiDA's optional
  exposed namespace with `populate_defaults: False` plus a conditional outline
  step is the idiomatic form — which matters more for a GUI consumer such as
  AiiDALab, where a single entry point with a branching form is worth more than
  it is at the Python API level.
- **Not a Mantid/AbINS replacement.** The aim is a faithful demonstration of the
  reference pipeline, not coverage of every scattering model AbINS supports.
- **No direct-geometry or 2-D (|Q|, ω) spectra.** TOSCA is indirect-geometry and
  produces 1-D spectra.
- **No coherent scattering, no single-crystal spectra.** Only the almost-isotropic
  incoherent approximation that `abinslib` 0.1 implements.
- **No new Data node type for spectra.** Spectra land in native `XyData`, keeping
  the existing "prefer AiiDA-native types for results" stance.
- **No tracking of the `abinslib` API beyond 0.1.** The pin is deliberate; adapting
  to the announced API change is a separate change.
- **No phonon calculation for ethanol.** The bundled modes are taken as given
  input; reproducing the underlying MLIP calculation is out of scope.
- **Quartz is not retired.** The existing dispersion and DOS tutorials keep their
  quartz input; ethanol is added for the TOSCA case rather than substituted
  everywhere.

## Impact

- **Code**: new TOSCA functions in `operations.py` and a matching `pythonjobs.py`
  builder; new `workflows/tosca.py` holding both chains and the grouping and
  broadening `calcfunction`s; three new conversion functions in `conversions.py`;
  a new serializer entry in `serialization.py`. No new loading code: modes enter
  through the existing `from_json_file` constructor.
- **Data**: one new bundled test/example file (~310 kB), with its provenance and
  licence recorded next to it, plus a follow-up to source hydrogenous force
  constants for the `ToscaFromForceConstantsWorkChain` example.
- **Packaging**: two new runtime dependencies and two new `aiida.workflows`
  entry points in `pyproject.toml`. `abinslib` requires Python >=3.11 and
  `euphonic>=2.0,<3`, both already satisfied, so the supported Python range is
  unchanged.
- **Docs**: two new gallery examples, adding to documentation build time.
- **Tests**: new test module for the TOSCA operations and workflow; the
  collection round trip and label helper join the existing conversion tests.
- **Risk**: both new dependencies are alpha. The narrow pins contain that, but
  they also constrain co-installed plugins — a tension with the packaging
  capability's preference for wide bounds, and one the design should address
  explicitly.
- **Open design question**: how metadata is encoded into an `XyData` array name
  must survive AiiDA's array-name constraints and round-trip unambiguously; the
  encoding is a design decision, not a spec one, but the round-trip guarantee is
  specified.
- **Deferred input**: a molecular-crystal force-constants dataset for the
  force-constants chain's example; quartz stands in, declared as atypical on the
  page, until a follow-up change replaces it.
- **Deliberately not refactored**: the existing `DosWorkChain` and
  `DispersionWorkChain` keep inheriting `ForceConstantsWorkChain` rather than
  composing it. Converting them later would preserve their input and output ports
  (`expose_inputs` without a namespace keeps ports at the top level) but would add
  a called node to the provenance graph, shift exit-code semantics to sub-process
  failures, and rename outline steps; it would also require
  `ForceConstantsWorkChain` to gain a complete outline and a force-constants
  output. That is a self-contained follow-up, not a prerequisite here.
- **Naming**: the instrument-specific names (`tosca-spectra`,
  `ToscaFromModesWorkChain`, `ToscaFromForceConstantsWorkChain`,
  `pythonjob_ins.tosca_from_modes`, `pythonjob_ins.tosca_from_force_constants`)
  mean a future general scheme can be introduced alongside them without a rename
  or a deprecation cycle. Entry-point names mirror the class names, matching the
  existing `pythonjob_ins.dos`/`DosWorkChain` correspondence; a dotted grouping
  such as `pythonjob_ins.tosca.modes` was considered and can be adopted later
  without affecting anything else.
