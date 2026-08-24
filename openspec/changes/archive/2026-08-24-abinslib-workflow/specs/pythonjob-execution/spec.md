## MODIFIED Requirements

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
