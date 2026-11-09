# phonon-operations Specification

## Purpose

Provide the scientific lattice-dynamics calculations as plain Python functions
that are independent of AiiDA, so they can be unit-tested directly, reused
outside AiiDA, and executed in a remote environment that carries only scientific
dependencies.
## Requirements
### Requirement: Operations are independent of AiiDA

The scientific operations SHALL be importable and runnable without AiiDA being
configured, and nothing in their import chain SHALL import AiiDA. This keeps the
remote execution environment free of any requirement for an AiiDA profile,
configuration or database.

#### Scenario: Importing the operations does not pull in AiiDA

- **WHEN** the operations module is imported in an interpreter where AiiDA has not
  been imported and no AiiDA profile exists
- **THEN** the import succeeds
- **AND** no AiiDA module has been loaded as a result

#### Scenario: Operations run with no AiiDA profile loaded

- **WHEN** an operation is called directly, outside any AiiDA process
- **THEN** it computes and returns its Euphonic result without requiring a profile

### Requirement: Operations use only Euphonic's public API

The operations SHALL depend only on documented, public Euphonic interfaces, so
that behaviour is not tied to Euphonic internals that may change without notice.
In particular, band-structure logic SHALL reproduce the behaviour of Euphonic's
dispersion command-line tool without calling its private helpers.

#### Scenario: No private Euphonic names are used

- **WHEN** the operations module's imports and attribute accesses on Euphonic
  objects are inspected
- **THEN** no name beginning with an underscore is imported from or called on
  Euphonic

### Requirement: Force constants are read from supported calculator output

The operations SHALL read interatomic force constants from a CASTEP
`.castep_bin`/`.check` file, and from a Phonopy output set given its summary,
force-constants and optional Born-charges file names. The Phonopy force-constants
file SHALL be accepted in either HDF5 or Phonopy text format, the format being
recognised from the file name's extension. File names SHALL be resolved relative
to the working directory, so the same functions work whether files are local or
staged into a remote job directory.

#### Scenario: Reading CASTEP force constants

- **WHEN** the CASTEP reader is called with a CASTEP force-constants file
- **THEN** the result is equivalent to calling Euphonic's own CASTEP reader on the
  same file, this operation adding only logging

#### Scenario: Reading Phonopy force constants

- **WHEN** the Phonopy reader is called with a summary, force-constants and
  Born-charges file name
- **THEN** the result is equivalent to calling Euphonic's own Phonopy reader on the
  same files

#### Scenario: Reading Phonopy force constants from HDF5

- **WHEN** the Phonopy reader is called with a summary and an HDF5
  force-constants file whose name carries an HDF5 extension
- **THEN** the result is equivalent to calling Euphonic's own Phonopy reader on the
  same files

#### Scenario: Born charges are optional

- **WHEN** the Phonopy reader is called without a Born-charges file name
- **THEN** the force constants are read successfully, without LO-TO splitting data

### Requirement: A high-symmetry band path is generated from structure alone

The operations SHALL build a high-symmetry q-point path from a crystal structure
and a target q-point spacing, requiring no force constants. The path SHALL be
returned together with its indexed high-symmetry labels and the real-space cell,
and SHALL be expressed in the original cell so the q-points are valid inputs to
interpolation on that same crystal.

#### Scenario: A path is generated with labelled high-symmetry points

- **WHEN** a band path is requested for a spglib-style cell at a given q-point
  spacing
- **THEN** an array of fractional q-points is returned
- **AND** the high-symmetry points are labelled, with the zone centre rendered as
  the Γ character

#### Scenario: Interior zone-centre points are duplicated for LO-TO splitting

- **WHEN** a path is generated with gamma insertion enabled and the path passes
  through the zone centre other than at its ends
- **THEN** each such interior zone-centre q-point appears twice, so that LO-TO
  splitting can be represented

### Requirement: Phonon modes are interpolated at given q-points

The operations SHALL Fourier-interpolate phonon frequencies and eigenvectors from
force constants at an arbitrary set of fractional q-points, applying an acoustic
sum rule by default and retaining every requested q-point.

#### Scenario: Interpolation returns one set of branches per q-point

- **WHEN** modes are interpolated for a crystal of A atoms at N q-points
- **THEN** the returned frequencies have shape (N, 3A)

#### Scenario: Symmetry-equivalent q-points are not collapsed

- **WHEN** an explicit band path containing repeated or symmetry-equivalent
  q-points is interpolated
- **THEN** the result retains every q-point of the path, in order

### Requirement: A dispersion calculation combines path generation and interpolation

The operations SHALL provide a single call that derives the band path from the
force constants' own crystal and interpolates the modes along it.

#### Scenario: Dispersion computed from force constants alone

- **WHEN** a dispersion is requested for a set of force constants at a given
  q-point spacing
- **THEN** phonon modes are returned covering more than one q-point, with three
  branches per atom of the crystal, finite throughout
- **AND** with the acoustic sum rule applied, the three acoustic branches vanish
  at the zone centre to within the residual the sum rule leaves

### Requirement: Imaginary frequencies are preserved and reported honestly

A dynamical matrix can yield negative eigenvalues, whose frequencies are imaginary
and are conventionally represented as negative values. These arise both from
genuine dynamical instability and, near the zone centre, from numerical noise in
the acoustic branches. Both cases are scientifically meaningful and must reach the
user. Operations SHALL propagate imaginary frequencies unaltered: they SHALL NOT
be clipped to zero, discarded, or replaced by their magnitude.

#### Scenario: Imaginary modes reach the caller unchanged

- **WHEN** interpolation yields one or more imaginary frequencies, represented as
  negative values
- **THEN** they appear in the returned modes with their sign intact, and no mode is
  removed, reordered or rescaled

#### Scenario: Instability is not disguised as a stable result

- **WHEN** a structure is dynamically unstable, so a substantial number of modes
  are imaginary
- **THEN** the returned modes represent that honestly, rather than presenting a
  spectrum that appears stable

### Requirement: A phonon density of states is computed on a sampling grid

The operations SHALL compute a phonon density of states by sampling a
Monkhorst-Pack grid derived from a target spacing, binning frequencies onto an
energy axis of configurable width and unit. Adaptive broadening based on mode
gradients SHALL be available and SHALL be the default.

#### Scenario: A density of states is returned as a spectrum

- **WHEN** a DOS is requested for a set of force constants at a given grid spacing
  and energy bin width
- **THEN** a non-empty `Spectrum1D` is returned whose bin centres and values have
  equal length, whose values are non-negative and not uniformly zero, and whose
  energy axis uses the requested bin width and covers the full phonon frequency range
  including imaginary/negative frequencies
- **AND** the spectrum integrates to three modes per atom of the crystal within
  the tolerance broadening allows

#### Scenario: The energy axis is generated from the computed frequencies

- **WHEN** a DOS is computed and the energy range is generated automatically
- **THEN** the axis uses the requested bin width, applies 5% padding above the maximum computed frequency, and:
  - if the minimum computed frequency is negative (imaginary modes present), applies 5% padding below that minimum frequency;
  - if the minimum computed frequency is non-negative, clamps the lower bound cleanly at zero without bottom padding
- **AND** all computed modes fall within the binned energy range, contributing their full weight to the integrated spectrum

#### Scenario: Adaptive broadening can be disabled

- **WHEN** a DOS is requested with adaptive broadening disabled
- **THEN** a valid spectrum is still returned, computed without mode gradients, and
  it satisfies the same sum rule at least as closely as the adaptive result, which
  loses slightly more weight to broadening beyond the binned range

### Requirement: Operations report progress through logging only

The operations SHALL emit informative progress messages through the Python
logging system. As library code they SHALL NOT configure logging handlers or
levels, and SHALL NOT write to standard output directly, so the host application
or AiiDA decides how messages surface.

#### Scenario: Progress messages are emitted at INFO level

- **WHEN** force constants are read and a dispersion is computed with INFO-level
  capture enabled for the operations logger
- **THEN** records are captured reporting the file being read, the size of the
  generated band path, and the number of modes and q-points being computed

#### Scenario: No output is printed directly

- **WHEN** an operation runs without any logging configuration
- **THEN** nothing is written to standard output by the operation itself

