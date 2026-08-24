# pythonjob-execution Specification

## Purpose

Run the scientific operations as AiiDA processes through the `aiida-pythonjob`
Python-API execution model, translating automatically between AiiDA nodes and
Euphonic objects so that scientific code stays free of workflow infrastructure
while provenance is still recorded.

## Requirements

### Requirement: Each operation can be launched as an AiiDA process

The plugin SHALL provide an input builder for every operation intended to run as
a job: reading CASTEP force constants, reading Phonopy force constants,
interpolating phonon modes, computing a dispersion, computing a density of
states, and computing scattering intensities for a spectrometer. Each builder
SHALL return inputs that can be launched directly as an AiiDA `PythonJob`, and
each SHALL yield a scientifically valid result rather than merely a node of the
expected type.

#### Scenario: A dispersion job produces phonon modes along a band path

- **WHEN** dispersion inputs are built from a force-constants node and launched
- **THEN** the process finishes successfully and its result is a
  `QpointPhononModesData` node
- **AND** the modes span a band path of more than one q-point, carry three
  branches per atom of the crystal, and are finite throughout
- **AND** with the acoustic sum rule applied, the three acoustic branches vanish
  at the zone centre to within the residual the sum rule leaves

#### Scenario: A density-of-states job produces a physically valid spectrum

- **WHEN** DOS inputs are built from a force-constants node and launched with a
  given sampling spacing and energy bin width
- **THEN** the process finishes successfully and its result is an `XyData` node
- **AND** the spectrum is non-empty, its values are non-negative and not uniformly
  zero, and its energy axis uses the requested bin width and covers the phonon
  frequency range
- **AND** the spectrum integrates to three modes per atom of the crystal, allowing
  for the small loss where broadening extends beyond the binned range

#### Scenario: A Phonopy read job produces a force-constants node

- **WHEN** Phonopy read inputs are built from summary, force-constants and Born
  files and launched
- **THEN** the process finishes successfully and its result is a
  `ForceConstantsData` node equivalent to reading the same files directly with
  Euphonic

#### Scenario: A scattering-intensity job produces a multi-line spectrum node

- **WHEN** scattering-intensity inputs are built from a `QpointPhononModesData`
  node and launched with a sample temperature, energy axis parameters and
  scattering angles
- **THEN** the process finishes successfully and its result is an `XyData` node
- **AND** the node holds one line per contributing atom, quantum order and
  scattering angle, each labelled and each of the same length as the energy axis
- **AND** the intensities are finite, non-negative and not uniformly zero

### Requirement: Custom data nodes are translated at the process boundary

Because a job function runs without an AiiDA profile, it SHALL receive and return
plain Python objects only. The plugin SHALL supply the translations that convert
its node types to Euphonic objects on the way in, and Euphonic results back to
nodes on the way out, so that callers pass and receive nodes while the scientific
function sees only Euphonic types.

#### Scenario: A force-constants node is presented to the function as a Euphonic object

- **WHEN** a `ForceConstantsData` node is supplied as a job input
- **THEN** the function receives a Euphonic `ForceConstants` object

#### Scenario: A q-point path node is presented as an array

- **WHEN** a `KpointsData` node is supplied as the q-point specification for
  interpolation
- **THEN** the function receives an array of fractional q-points

#### Scenario: Euphonic results are stored as the appropriate node type

- **WHEN** a function returns a `ForceConstants`, a `QpointPhononModes`, or a
  `Spectrum1D`
- **THEN** the process output is respectively a `ForceConstantsData`, a
  `QpointPhononModesData`, or an `XyData` node

#### Scenario: A job function never constructs a node

- **WHEN** any job function executes in the remote interpreter
- **THEN** it returns plain Python objects and requires no AiiDA profile,
  configuration or database connection

### Requirement: Input files are staged into the job working directory

Where an operation reads files, those files SHALL be staged into the job's
working directory and referenced by base name, mirroring how a real remote
calculation receives its inputs. Files SHALL be accepted either as a path or as a
`SinglefileData` node.

#### Scenario: A CASTEP file is staged for a read job

- **WHEN** a CASTEP read job is built from a file path or a `SinglefileData`
- **THEN** the file is staged into the working directory and the function is given
  only its base name

#### Scenario: A Phonopy input set is staged together

- **WHEN** a Phonopy read job is built with summary and force-constants files, and
  optionally a Born-charges file
- **THEN** all supplied files are staged into the same working directory and
  referenced by base name
- **AND** the Born-charges file is omitted entirely when not supplied

### Requirement: Wrapped execution reproduces a direct Euphonic calculation

Running any compute operation as an AiiDA process SHALL produce the same
scientific result as calling the underlying Euphonic public API directly with the
same parameters, to within the numerical tolerance expected from running in a
separate interpreter.

#### Scenario: Dispersion via a job matches a direct call

- **WHEN** a dispersion is computed both directly in-process and by launching the
  equivalent job
- **THEN** the two sets of frequencies agree within a relative tolerance of 1e-3
  and an absolute tolerance of 0.05 meV, which absorbs eigensolver noise on
  near-degenerate acoustic modes

#### Scenario: Interpolation from a path node matches a direct call

- **WHEN** modes are interpolated both directly and by launching the equivalent
  job driven by a `KpointsData` path
- **THEN** the frequencies agree within the same tolerances

#### Scenario: A density of states via a job matches a direct call

- **WHEN** a density of states is computed both directly and by launching the
  equivalent job with the same sampling spacing and energy bin width
- **THEN** the two spectra agree bin for bin on the same energy axis

### Requirement: Execution targets are standard AiiDA Computer and Code inputs

Jobs SHALL be directed at a `Computer` and an `AbstractCode` in the ordinary AiiDA
way, so the same code can run on localhost or on a remote scheduler without
modification. The code SHALL be a Python interpreter in an environment where the
job's dependencies are importable.

#### Scenario: A caller supplies an explicit code

- **WHEN** an input builder is given an `AbstractCode`
- **THEN** the job runs through that code on its associated computer

#### Scenario: A workflow requires an explicit code

- **WHEN** a workflow is launched
- **THEN** an `AbstractCode` must be supplied; the workflow neither selects nor
  creates one on the caller's behalf

### Requirement: Job functions are shipped by reference

Job functions SHALL be transferred to the execution environment by module
reference rather than by value, keeping submission payloads and stored provenance
small at production scale. The execution environment must therefore have this
package importable, alongside the scientific dependencies the function uses.

#### Scenario: Submission transfers a reference, not the function body

- **WHEN** a job is submitted
- **THEN** only a module and function reference is transferred
- **AND** the execution environment must have this package and its scientific
  dependencies importable

#### Scenario: Additional process options are forwarded

- **WHEN** a caller passes extra keyword arguments to an input builder
- **THEN** they are forwarded unchanged to the inputs of the underlying process
