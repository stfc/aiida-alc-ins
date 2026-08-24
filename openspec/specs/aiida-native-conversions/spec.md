# aiida-native-conversions Specification

## Purpose

Express Euphonic inputs and results in AiiDA's native materials-science data
types, so that structures, q-point paths, band structures and spectra can be
consumed by existing AiiDA tooling instead of requiring Euphonic-specific code.

## Requirements

### Requirement: Crystal structures convert between Euphonic and AiiDA

A Euphonic `Crystal` SHALL convert to a native AiiDA `StructureData` and back,
preserving the lattice, the atomic species, the atomic positions and the atomic
masses. The conversion SHALL use AiiDA's native structure API and SHALL NOT
require ASE.

#### Scenario: A crystal becomes a periodic StructureData

- **WHEN** a Euphonic `Crystal` is converted to a `StructureData`
- **THEN** the structure has one site per atom, positions expressed in Cartesian
  coordinates, per-kind masses carried over, and periodic boundary conditions set
  in all three directions

#### Scenario: A structure converts back to an equivalent crystal

- **WHEN** a `StructureData` produced from a crystal is converted back to a
  Euphonic `Crystal`
- **THEN** the rebuilt crystal has the same lattice vectors, atomic species,
  fractional positions and atomic masses as the original, to within numerical
  tolerance
- **AND** the round trip is therefore usable in a calculation, not only as a
  record of the structure

#### Scenario: A structure is expressed as a spglib cell

- **WHEN** a `StructureData` is converted to a spglib-style cell
- **THEN** a `(lattice, positions, numbers)` tuple describing the same structure
  is returned

### Requirement: q-points are represented as a native KpointsData

A set of fractional q-points, together with the real-space cell and any
high-symmetry labels, SHALL be representable as a native AiiDA `KpointsData`, so
that a phonon band path is an ordinary AiiDA reciprocal-space object.

#### Scenario: q-points and labels round-trip through KpointsData

- **WHEN** fractional q-points, a cell and a list of indexed labels are converted
  to a `KpointsData`
- **THEN** reading the q-points back returns the original positions
- **AND** the stored labels match the labels supplied

### Requirement: Phonon modes compose into a native BandsData

Phonon frequencies evaluated on a q-point path SHALL be expressible as a native
AiiDA `BandsData`, treating frequencies as band energies in meV, so that AiiDA's
existing band-structure tooling can plot and export them.

#### Scenario: Modes become bands with matching dimensions

- **WHEN** a `QpointPhononModes` object covering N q-points for a crystal of A
  atoms is converted to a `BandsData`
- **THEN** the resulting bands array has shape (N, 3A)

#### Scenario: High-symmetry labels are taken from the supplied path

- **WHEN** the conversion is given the `KpointsData` band path used to compute the
  modes
- **THEN** the resulting `BandsData` carries that path's q-point positions and its
  high-symmetry labels

#### Scenario: Labels fall back to Euphonic's automatic ticks

- **WHEN** the conversion is performed without a `KpointsData` path
- **THEN** q-point positions are taken from the modes themselves and at least one
  high-symmetry label is derived automatically

#### Scenario: Imaginary frequencies survive the composition

- **WHEN** modes containing imaginary frequencies, represented as negative values,
  are composed into a `BandsData`
- **THEN** those values are carried through with their sign intact, so a plot shows
  them below the zero line rather than concealing them

#### Scenario: A band structure renders without AiiDALab

- **WHEN** a `BandsData` composed from phonon modes is exported as a matplotlib
  PNG
- **THEN** a non-empty image file is produced, with no AiiDALab dependency

### Requirement: An inconsistent band path is rejected

When composing a `BandsData` from modes and an explicit q-point path, the
conversion SHALL verify that the path and the modes describe the same
calculation, and SHALL raise `ValueError` if they do not, rather than silently
producing a mislabelled band structure.

#### Scenario: Mismatched q-points are rejected

- **WHEN** the supplied `KpointsData` holds q-points that differ from those of the
  phonon modes
- **THEN** a `ValueError` is raised stating that the path and the computed modes
  are inconsistent

#### Scenario: A mismatched cell is rejected

- **WHEN** the supplied `KpointsData` holds a cell that differs from the modes'
  crystal cell
- **THEN** a `ValueError` is raised explaining that fractional coordinates would
  refer to a different lattice

### Requirement: Spectra convert to a native XyData

A single Euphonic `Spectrum1D` SHALL convert to a native AiiDA `XyData` whose x and y arrays are the same length and whose units
are recorded.

A Euphonic `Spectrum1DCollection`, which shares one x axis across several y
columns, SHALL likewise convert to a single native `XyData` carrying one y array
per column. Because a collection's columns are distinguished only by their
metadata, that metadata SHALL be preserved on the node rather than discarded: the
conversion SHALL be reversible, so that a collection recovered from the node
carries the same per-column metadata as the original and can be grouped, selected
and summed by that metadata exactly as the original could.

Each y array SHALL additionally be named with a concise, human-readable label
derived from the column's metadata, so that a consumer reading the node can plot
and label its lines without interpreting the metadata itself.

#### Scenario: A density of states becomes plottable XyData

- **WHEN** a DOS `Spectrum1D` is converted to an `XyData`
- **THEN** the x array holds the spectrum's bin centres rather than its bin edges
- **AND** the y array holds the corresponding spectrum values
- **AND** both arrays are labelled with the units taken from the spectrum

#### Scenario: A collection becomes one XyData with one y array per line

- **WHEN** a `Spectrum1DCollection` is converted to an `XyData`
- **THEN** the node holds a single x array of the collection's bin centres
- **AND** it holds one y array per line of the collection, each of the same length
  as the x array
- **AND** the units of the x and y arrays are taken from the collection

#### Scenario: Metadata survives the round trip

- **WHEN** a `Spectrum1DCollection` is converted to an `XyData` and then converted
  back
- **THEN** the recovered collection has the same number of lines, the same x and y
  values, and the same metadata both common to the collection and specific to each
  line

#### Scenario: Recovered metadata supports grouping

- **WHEN** a collection recovered from an `XyData` is grouped by a metadata key
  present on its lines
- **THEN** the grouping yields the same result as grouping the original collection
  by that key

#### Scenario: Line labels are readable without parsing metadata

- **WHEN** a `Spectrum1DCollection` whose lines differ in their metadata is
  converted to an `XyData`
- **THEN** each y array is named with a label distinguishing that line from the
  others, derived from the metadata that varies between them
- **AND** the label is suitable for direct use as a plot legend entry
