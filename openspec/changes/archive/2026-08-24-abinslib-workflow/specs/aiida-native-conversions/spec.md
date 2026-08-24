## MODIFIED Requirements

### Requirement: Spectra convert to a native XyData

A Euphonic `Spectrum1D`, such as a phonon density of states, SHALL convert to a
native AiiDA `XyData` whose x and y arrays are the same length and whose units
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
