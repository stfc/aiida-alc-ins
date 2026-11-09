# phonon-workflows Specification

## Purpose

Compose the individual phonon steps into end-to-end AiiDA workflows that turn
force constants -- or previously computed phonon modes -- into vibrational
properties such as a band structure, a density of states or an inelastic-neutron-
scattering spectrum, recording the whole calculation as a single connected
provenance graph.
## Requirements

### Requirement: Workflows accept exactly one source of force constants

Every workflow that starts from force constants SHALL obtain them from one of: a
CASTEP file, read during the workflow; a Phonopy file set, read during the
workflow; or a prepared force-constants node supplied by the caller. Exactly one
of the three SHALL be given, and the workflow SHALL reject inputs that provide
more than one or none before any computation begins.

The source inputs SHALL be grouped under a single `force_constants` input
namespace whose ports are those of `ForceConstantsWorkChain`: `castep_file` for a
CASTEP file, a `phonopy` namespace for a Phonopy file set, and `node` for a
prepared node.

A workflow whose input is a different quantity — such as one that starts from
prepared phonon modes — SHALL NOT offer a force-constants source at all, rather
than offering one that is optional or ignored.

#### Scenario: A CASTEP file is supplied

- **WHEN** a workflow is launched with a CASTEP `SinglefileData` and no other
  force-constants source
- **THEN** the workflow reads the force constants as its first step and proceeds

#### Scenario: A Phonopy file set is supplied

- **WHEN** a workflow is launched with a Phonopy file set and no other
  force-constants source
- **THEN** the workflow reads the force constants as its first step and proceeds

#### Scenario: A prepared node is supplied

- **WHEN** a workflow is launched with a `ForceConstantsData` node and no other
  force-constants source
- **THEN** the workflow uses that node directly and performs no read step

#### Scenario: Both sources are supplied

- **WHEN** a workflow is launched with any two of a CASTEP file, a Phonopy file
  set and a force-constants node
- **THEN** the workflow is rejected with an error stating that exactly one source
  must be provided, naming all three

#### Scenario: All three sources are supplied

- **WHEN** a workflow is launched with a CASTEP file, a Phonopy file set and a
  force-constants node together
- **THEN** the workflow is rejected with the same error

#### Scenario: Neither source is supplied

- **WHEN** a workflow is launched with no CASTEP file, no Phonopy file set and no
  force-constants node
- **THEN** the workflow is rejected with the same error

#### Scenario: Source inputs are grouped in one namespace

- **WHEN** the inputs of a workflow that starts from force constants are inspected
- **THEN** the CASTEP file port, the Phonopy namespace and the force-constants
  node port appear only inside its `force_constants` namespace, with the same
  names as the inputs of `ForceConstantsWorkChain`

#### Scenario: A workflow starting from another quantity has no force-constants input

- **WHEN** the inputs of a workflow that starts from prepared phonon modes are
  inspected
- **THEN** they include no CASTEP file, no Phonopy file set and no
  force-constants node

### Requirement: Force constants are resolved by a standalone workflow

`ForceConstantsWorkChain` SHALL accept exactly one force-constants source: a
CASTEP file, a Phonopy file set, or a `ForceConstantsData` node. It SHALL output
the resolved `ForceConstantsData` as `force_constants`. It SHALL dispatch no jobs
and SHALL NOT take a `Code` or execution options.

A Phonopy file set SHALL be given as `SinglefileData` nodes under a `phonopy`
namespace: `summary`, the Phonopy summary file, which is required whenever the
namespace is used; `force_constants`, a force-constants file in HDF5 or Phonopy
text format, which is optional; and `born`, a Born-charges file, which is
optional.

#### Scenario: A CASTEP file is resolved

- **WHEN** the workflow is launched with a CASTEP `SinglefileData`
- **THEN** it outputs a `ForceConstantsData` equivalent to reading the same file
  with Euphonic's own CASTEP reader
- **AND** the read appears as its own calculation in the provenance graph,
  linking the file to the output

#### Scenario: A Phonopy file set with HDF5 force constants is resolved

- **WHEN** the workflow is launched with a Phonopy summary and an HDF5
  force-constants file
- **THEN** it outputs a `ForceConstantsData` equivalent to reading the same files
  with Euphonic's own Phonopy reader
- **AND** the read appears as its own calculation in the provenance graph,
  linking every supplied file to the output

#### Scenario: A Phonopy file set with text force constants is resolved

- **WHEN** the workflow is launched with a Phonopy summary and a text-format
  force-constants file
- **THEN** it outputs a `ForceConstantsData` equivalent to reading the same files
  with Euphonic's own Phonopy reader

#### Scenario: Born charges are passed through when supplied

- **WHEN** the workflow is launched with a Phonopy file set that includes a
  Born-charges file
- **THEN** the output is equivalent to Euphonic's own Phonopy reader given the
  same Born-charges file, including any LO-TO splitting data it yields

#### Scenario: A summary that embeds force constants needs no separate file

- **WHEN** the workflow is launched with only a Phonopy summary that itself
  contains force constants
- **THEN** it outputs a `ForceConstantsData` equivalent to reading that summary
  with Euphonic's own Phonopy reader

#### Scenario: A Phonopy file set without a summary is rejected

- **WHEN** the workflow is launched with a `phonopy` namespace that has a
  force-constants or Born-charges file but no summary
- **THEN** the workflow is rejected before any computation begins

#### Scenario: A prepared node is passed through

- **WHEN** the workflow is launched with a `ForceConstantsData` node
- **THEN** its `force_constants` output is that same node, and no calculation is
  performed

#### Scenario: No code or options are accepted

- **WHEN** the inputs of the workflow are inspected
- **THEN** they include neither a code nor an options input

#### Scenario: An unreadable file fails with a dedicated exit code

- **WHEN** the workflow is launched with a file that cannot be read as CASTEP
  force constants
- **THEN** it terminates with an exit code dedicated to read failure and emits no
  output

#### Scenario: An unreadable Phonopy file set fails with the same exit code

- **WHEN** the workflow is launched with a Phonopy file set from which force
  constants cannot be read, whether because a file is malformed or because
  neither the summary nor a separate file supplies force constants
- **THEN** it terminates with the same read-failure exit code as for an
  unreadable CASTEP file and emits no output

### Requirement: Force-constants workflows delegate source resolution

Every workflow that starts from force constants SHALL obtain them by running
`ForceConstantsWorkChain` as a sub-workflow, whichever source is supplied. If the
sub-workflow does not finish successfully, the workflow SHALL stop with an exit
code dedicated to that failure, distinct from its other exit codes, and SHALL emit
no outputs.

#### Scenario: The source workflow appears in provenance

- **WHEN** a workflow that starts from force constants runs, from any kind of
  source
- **THEN** exactly one `ForceConstantsWorkChain` appears as a called sub-workflow
- **AND** its `force_constants` output is the node the subsequent steps consume

#### Scenario: A failed source resolution stops the workflow

- **WHEN** the `ForceConstantsWorkChain` sub-workflow does not finish successfully
- **THEN** the workflow terminates with its dedicated source-failure exit code,
  distinct from the code used for a failed job step
- **AND** no outputs are emitted

### Requirement: The dispersion workflow produces a labelled band structure

The dispersion workflow SHALL derive the crystal structure from the force
constants, generate a high-symmetry q-point path from it, interpolate the phonon
modes along that path, and compose a band structure. It SHALL expose the phonon
modes, the structure, the band path and the band structure as separate outputs,
so that intermediate results remain available and provenance-linked.

#### Scenario: All four outputs are produced with native types

- **WHEN** the dispersion workflow completes successfully
- **THEN** it outputs a `QpointPhononModesData`, a `StructureData`, a
  `KpointsData` band path, and a `BandsData` band structure

#### Scenario: The band path carries high-symmetry labels

- **WHEN** the dispersion workflow completes
- **THEN** the output band path has labelled high-symmetry points

#### Scenario: Band structure dimensions match the path and the modes

- **WHEN** the dispersion workflow completes for a crystal of A atoms
- **THEN** the band structure has one row per q-point in the band path and 3A
  branches per row

#### Scenario: The q-point spacing is configurable

- **WHEN** the workflow is launched without specifying a q-point spacing
- **THEN** a default target spacing of 0.025 reciprocal angstroms is applied

### Requirement: The DOS workflow produces a plottable density of states

The density-of-states workflow SHALL sample a Monkhorst-Pack grid from the force
constants and output the resulting density of states as a native `XyData`.

#### Scenario: A density of states is output

- **WHEN** the DOS workflow completes successfully
- **THEN** it outputs an `XyData` holding a physically valid density of states:
  non-empty, with energy and value arrays of equal length, values non-negative and
  not uniformly zero, whose energy axis covers all computed modes (including any negative/imaginary frequencies),
  and integrating to three modes per atom of the crystal within
  the tolerance broadening allows

#### Scenario: Grid and energy spacing are configurable

- **WHEN** the workflow is launched without specifying spacings
- **THEN** a default grid spacing of 0.1 reciprocal angstroms and a default energy
  bin width of 1.0 meV are applied

### Requirement: Compute steps are dispatchable to a Computer

Computationally heavy steps SHALL execute through a `Code` on a `Computer`, so a
workflow can be directed at a remote machine without modification. Every step SHALL
be recorded in the provenance graph.

The workflow SHALL accept an optional `options` input port (holding a `Dict` or dictionary
describing scheduler and execution options, such as resources, wallclock limits, or queue names)
and SHALL forward these options to every dispatched job step. When `options` is not supplied,
the default execution options of the underlying job step SHALL apply.

Reading force constants from a file, and regrouping or broadening an
already-computed spectrum, are cheap by comparison. They SHALL NOT be dispatched
through the `Code`, and SHALL each be recorded as their own step in the provenance
graph so that they can be repeated independently of the heavy work.

#### Scenario: Heavy steps run through the supplied code

- **WHEN** a workflow runs
- **THEN** mode interpolation, density-of-states sampling and
  scattering-intensity calculation each execute through the supplied code rather
  than in the caller's process
- **AND** each appears as a calculation in the workflow's provenance graph

#### Scenario: Reading force constants is recorded but not dispatched

- **WHEN** a workflow runs from a CASTEP `SinglefileData`
- **THEN** reading the force constants does not execute through the supplied code
- **AND** it appears as its own calculation in the provenance graph, linking the
  `SinglefileData` to the `ForceConstantsData` it produces

#### Scenario: Caller supplies scheduler options to the workflow

- **WHEN** a workflow is launched with an `options` input specifying scheduler resources
- **THEN** each dispatched `PythonJob` calculation executes with those resources configured in its metadata options
- **AND** the `options` node is linked as an input in the workflow's provenance graph

#### Scenario: Caller omits scheduler options

- **WHEN** a workflow is launched without an `options` input
- **THEN** each dispatched `PythonJob` calculation executes with its standard default options

#### Scenario: A prepared force-constants node is not re-read

- **WHEN** a workflow runs from a `ForceConstantsData` node rather than a CASTEP
  file
- **THEN** no force-constants reading step is performed

#### Scenario: Cheap post-processing is recorded as its own step

- **WHEN** a workflow groups or broadens a spectrum it has already computed
- **THEN** that post-processing appears in the provenance graph as a step distinct
  from the calculation that produced the spectrum

#### Scenario: Outputs are provenance-linked to inputs

- **WHEN** a workflow completes
- **THEN** every output node is connected back to the workflow's inputs through the
  recorded steps

### Requirement: The TOSCA workflow produces an instrument-resolved spectrum

A workflow SHALL take prepared phonon modes and produce the inelastic-neutron-
scattering spectrum TOSCA would record from them, output as a native `XyData`.

Its scientific inputs — sample temperature, energy bin width, maximum energy,
scattering angles and resolution model — SHALL all be configurable, and SHALL
default to values representing a conventional TOSCA measurement.

#### Scenario: A spectrum is output

- **WHEN** the TOSCA workflow completes successfully from a `QpointPhononModesData`
  input
- **THEN** it outputs an `XyData` holding a physically valid spectrum: non-empty,
  with energy and intensity arrays of equal length, intensities finite,
  non-negative and not uniformly zero, and an energy axis using the requested bin
  width

#### Scenario: Instrument and sample parameters are configurable

- **WHEN** the workflow is launched without specifying temperature, bin width,
  maximum energy, scattering angles or resolution model
- **THEN** defaults representing a conventional TOSCA measurement are applied, with
  both detector banks evaluated

#### Scenario: Modes are required as a node

- **WHEN** the workflow is launched
- **THEN** its phonon modes are supplied as a `QpointPhononModesData` node, and no
  file-reading step is performed

### Requirement: The full line set is recorded before it is grouped

The TOSCA workflow SHALL commit the complete, ungrouped set of spectrum lines to
the provenance graph as its own output before any grouping is applied, and SHALL
perform grouping as a later, separate step.

The caller SHALL be able to specify which metadata keys to group by; supplying no
keys SHALL yield a single total spectrum. Grouping SHALL sum the lines that share
the values of the specified keys.

Recording the ungrouped result separately is required so that repeating the
workflow with different grouping or a different resolution model can reuse the
committed intensity calculation instead of repeating it.

#### Scenario: Both the components and the grouped result are output

- **WHEN** the TOSCA workflow completes successfully
- **THEN** it outputs the full set of spectrum lines, one per contributing atom,
  quantum order and detector bank
- **AND** it outputs the grouped spectrum derived from them

#### Scenario: Grouping keys select how lines are combined

- **WHEN** the workflow is launched with a set of metadata keys to group by
- **THEN** the grouped output contains one line per distinct combination of values
  of those keys, each the sum of the contributing lines

#### Scenario: No grouping keys yields a total

- **WHEN** the workflow is launched without grouping keys
- **THEN** the grouped output is a single spectrum, the sum of all lines

#### Scenario: Regrouping reuses the committed intensity calculation

- **WHEN** the workflow is run a second time with caching enabled, identical inputs
  except for the grouping keys
- **THEN** the intensity calculation is taken from the cache rather than repeated
- **AND** the newly grouped result is still produced and provenance-linked

#### Scenario: Grouped intensity is conserved

- **WHEN** the lines of the grouped output are summed
- **THEN** the result equals the sum of all lines of the ungrouped output, to
  numerical precision

### Requirement: A force-constants-sourced TOSCA workflow composes the modes workflow

A second workflow SHALL start from force constants, sample q-points from them, and
delegate the spectrum calculation to the modes-based TOSCA workflow rather than
reimplementing it, exposing that workflow's scientific inputs and outputs as its
own.

Sampling parameters that are meaningful only when starting from force constants
SHALL exist on this workflow alone, and SHALL NOT appear on the modes-based
workflow.

#### Scenario: The force-constants workflow produces the same kind of result

- **WHEN** the force-constants-sourced TOSCA workflow completes successfully
- **THEN** it outputs the same spectrum outputs as the modes-based workflow

#### Scenario: The delegation is visible in the provenance graph

- **WHEN** the force-constants-sourced TOSCA workflow runs
- **THEN** the modes-based workflow appears in its provenance graph as a called
  sub-workflow, with the interpolated modes linking the two

#### Scenario: Sampling parameters are absent from the modes-based workflow

- **WHEN** the inputs of the modes-based TOSCA workflow are inspected
- **THEN** they contain no q-point sampling parameter, that parameter belonging
  only to the force-constants-sourced workflow

#### Scenario: A failure in the delegated workflow is distinguishable

- **WHEN** the delegated modes-based workflow does not finish successfully
- **THEN** the force-constants-sourced workflow stops and returns an exit code
  distinct from the one used for a failure of its own force-constants step

### Requirement: A failed step terminates the workflow with a distinct exit code

If a step does not finish successfully, the workflow SHALL stop and return a
dedicated failure exit code rather than proceeding with missing results.

#### Scenario: A job step fails

- **WHEN** any `PythonJob` step of a workflow finishes unsuccessfully
- **THEN** the workflow terminates with exit code 400, reporting that a job step
  did not finish successfully
- **AND** no downstream outputs are emitted

#### Scenario: Force constants cannot be read

- **WHEN** a workflow is launched with a file that cannot be read as CASTEP force
  constants, including truncated binary data, corrupt record markers, unsupported
  CASTEP versions, or calculation outputs lacking force constants
- **THEN** the workflow terminates with an exit code dedicated to failing to
  obtain force constants, distinct from exit code 400, reporting why
- **AND** no downstream outputs are emitted
