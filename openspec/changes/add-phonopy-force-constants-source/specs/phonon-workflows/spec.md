## MODIFIED Requirements

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
