## Purpose

Provide the simulated inelastic-neutron-scattering spectrum that the TOSCA
spectrometer would record from a set of phonon modes, as plain Python
calculations independent of AiiDA, so they can be unit-tested directly, reused
outside AiiDA, and executed in a remote environment carrying only scientific
dependencies.

## ADDED Requirements

### Requirement: Spectrum calculation is independent of AiiDA

The TOSCA spectrum calculation SHALL be importable and runnable without AiiDA
being installed or a profile being loaded, and SHALL return Euphonic objects
rather than AiiDA nodes. It SHALL report progress through logging only, never by
writing to standard output.

#### Scenario: Running without AiiDA

- **WHEN** the spectrum calculation is imported and called in an environment where
  AiiDA is absent
- **THEN** it completes and returns a Euphonic `Spectrum1DCollection`

#### Scenario: Progress is reported through logging

- **WHEN** the spectrum calculation runs
- **THEN** any progress information is emitted through the logging system, and
  nothing is written to standard output

### Requirement: Every detector bank requested is sampled and identifiable

TOSCA's detector banks sit at different scattering angles, each imposing its own
relationship between energy transfer and accessible momentum transfer. The
calculation SHALL evaluate that kinematic relationship separately for every
requested scattering angle, and SHALL record the angle each spectrum line belongs
to in that line's metadata under `detector_angle`, so lines from different banks
remain separable after the spectra are combined.

By default both of TOSCA's banks SHALL be evaluated.

#### Scenario: Both banks are computed by default

- **WHEN** the spectrum calculation runs without an explicit choice of scattering
  angles
- **THEN** the result contains lines for both the backward and forward detector
  banks
- **AND** every line records its own scattering angle in its metadata

#### Scenario: A single bank is requested

- **WHEN** the spectrum calculation runs for one scattering angle
- **THEN** the result contains lines for that angle only, and each records it

#### Scenario: Different banks give different kinematics

- **WHEN** the same modes are evaluated at two different scattering angles
- **THEN** the resulting momentum transfer at a given energy transfer differs
  between them, and so do the resulting intensities

### Requirement: Fundamental and combination contributions are both included

The calculation SHALL compute both the one-phonon (fundamental) intensities and
the higher-order combination-mode intensities, and SHALL label every spectrum line
with the quantum order it represents and with the atom it arises from, under the
metadata keys `quantum_order` and `atom_symbol`.

#### Scenario: Contributions are separable by order and by element

- **WHEN** a spectrum is calculated
- **THEN** the result contains lines of more than one quantum order
- **AND** every line carries both its quantum order and its atom symbol in its
  metadata
- **AND** grouping the lines by either key partitions them without loss

#### Scenario: The total spectrum is physically plausible

- **WHEN** all lines of a calculated spectrum are summed
- **THEN** the resulting intensities are finite, non-negative and not uniformly
  zero

### Requirement: The energy axis is bounded by the instrument and clipped to the data

The energy axis SHALL cover the range in which intensity can appear, and no more.
Because combination modes extend to a multiple of the highest fundamental
frequency, the axis SHALL be sized from the fundamental frequencies scaled by the
highest quantum order computed, using the same padding and bin-alignment rules as
the density of states.

The axis SHALL additionally be limited by a caller-supplied maximum energy
representing the instrument's measurable range, and SHALL stop at whichever of the
two bounds is lower.

#### Scenario: Combination modes are not truncated

- **WHEN** a spectrum including combination modes is calculated for modes whose
  scaled range lies below the instrument maximum
- **THEN** the energy axis extends far enough to contain intensity from the
  highest-order combination of the highest fundamental frequencies

#### Scenario: The instrument maximum limits the axis

- **WHEN** the scaled frequency range would exceed the supplied maximum energy
- **THEN** the energy axis stops at that maximum

#### Scenario: The axis is clipped when the data do not reach the maximum

- **WHEN** the scaled frequency range falls short of the supplied maximum energy
- **THEN** the energy axis stops at the scaled frequency range rather than
  extending to the maximum

#### Scenario: The bin width is honoured

- **WHEN** a spectrum is calculated with a given energy bin width
- **THEN** the bins of the resulting spectrum have that width

### Requirement: Sample temperature governs the thermal displacements

The calculation SHALL take the sample temperature as an input and use it to derive
the thermal displacements that determine the Debye-Waller attenuation, so that a
spectrum computed at one temperature differs from the same spectrum computed at
another.

#### Scenario: Temperature changes the result

- **WHEN** the same modes are used to calculate spectra at two different sample
  temperatures
- **THEN** the resulting intensities differ

### Requirement: Instrument resolution broadening is applied and is linear

The calculation SHALL apply the instrument's energy-dependent resolution function
to a spectrum on request, using a caller-selectable resolution model. Because the
resolution operator is linear, broadening a summed spectrum SHALL give the same
result as summing the separately broadened contributions.

#### Scenario: Broadening is applied

- **WHEN** a resolution model is applied to a spectrum
- **THEN** the result is finite and non-negative throughout, and differs from the
  unbroadened spectrum

#### Scenario: Broadening commutes with summation

- **WHEN** a set of spectrum lines is broadened and then summed, and the same set
  is summed and then broadened
- **THEN** the two results agree to numerical precision

### Requirement: Results reproduce a direct calculation with the underlying library

The calculation SHALL be a faithful wrapper: for the same modes, temperature,
scattering angles, energy axis and resolution model, the result SHALL be equal to
performing the same sequence directly against the underlying spectrum and
resolution libraries' public interfaces.

#### Scenario: Equivalence with a direct calculation

- **WHEN** a spectrum is calculated through this capability and, separately, by
  calling the underlying libraries directly with the same inputs
- **THEN** the two spectra are equal, this capability adding only the energy-axis
  construction, the per-line metadata and logging
