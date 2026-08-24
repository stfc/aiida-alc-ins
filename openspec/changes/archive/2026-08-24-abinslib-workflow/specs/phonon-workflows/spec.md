## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Workflows accept exactly one source of force constants

Every workflow that starts from force constants SHALL obtain them from either a
CASTEP file, read during the workflow, or a prepared force-constants node supplied
by the caller. Exactly one of the two SHALL be given, and the workflow SHALL reject
inputs that provide both or neither before any computation begins.

A workflow whose input is a different quantity — such as one that starts from
prepared phonon modes — SHALL NOT offer a force-constants source at all, rather
than offering one that is optional or ignored.

#### Scenario: A CASTEP file is supplied

- **WHEN** a workflow is launched with a CASTEP `SinglefileData` and no
  force-constants node
- **THEN** the workflow reads the force constants as its first step and proceeds

#### Scenario: A prepared node is supplied

- **WHEN** a workflow is launched with a `ForceConstantsData` node and no CASTEP
  file
- **THEN** the workflow uses that node directly and performs no read step

#### Scenario: Both sources are supplied

- **WHEN** a workflow is launched with both a CASTEP file and a force-constants
  node
- **THEN** the workflow is rejected with an error stating that exactly one of the
  two must be provided

#### Scenario: Neither source is supplied

- **WHEN** a workflow is launched with neither a CASTEP file nor a force-constants
  node
- **THEN** the workflow is rejected with the same error

#### Scenario: A workflow starting from another quantity has no force-constants input

- **WHEN** the inputs of a workflow that starts from prepared phonon modes are
  inspected
- **THEN** they include no CASTEP file and no force-constants node

### Requirement: Compute steps are dispatchable to a Computer

Computationally heavy steps SHALL execute through a `Code` on a `Computer`, so a
workflow can be directed at a remote machine without modification. Every step SHALL
be recorded in the provenance graph.

The division of work between steps is an implementation concern and is not fixed
here; what is required is that heavy work is dispatchable, that no redundant work
is performed, and that the result is fully provenance-linked.

Steps that are cheap by comparison — such as regrouping or broadening an
already-computed spectrum — need not be dispatched, but SHALL still be recorded as
their own steps in the provenance graph so that they can be repeated
independently of the heavy work.

#### Scenario: Heavy steps run through the supplied code

- **WHEN** a workflow runs
- **THEN** force-constants reading, mode interpolation, density-of-states sampling
  and scattering-intensity calculation each execute through the supplied code
  rather than in the caller's process
- **AND** each appears as a calculation in the workflow's provenance graph

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
