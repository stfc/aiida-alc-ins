## MODIFIED Requirements

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
