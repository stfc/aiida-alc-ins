## ADDED Requirements

### Requirement: Cross-section weighting is applied to unweighted intensity contributions
The calculation SHALL explicitly apply neutron scattering cross-section weights to the unweighted raw intensity lines (both fundamentals and combination modes) before lines are grouped, producing physical intensities in cross-section-weighted units.

#### Scenario: Output intensities are cross-section weighted
- **WHEN** a TOSCA spectrum is calculated from phonon modes
- **THEN** each intensity line has its y-data scaled by the corresponding element's neutron scattering cross section
- **AND** the spectrum y-data has units of `barn * cm` (or `barn / energy`)

## MODIFIED Requirements

### Requirement: Results reproduce a direct calculation with the underlying library
The calculation SHALL be a faithful wrapper: for the same modes, temperature, scattering angles, energy axis and resolution model, the result SHALL be equal to performing the same sequence directly against the underlying spectrum, weighting, and resolution libraries' public interfaces.

#### Scenario: Equivalence with a direct calculation
- **WHEN** a spectrum is calculated through this capability and, separately, by calling the underlying libraries directly (including `apply_weights`) with the same inputs
- **THEN** the two spectra are equal, this capability adding only the energy-axis construction, the per-line metadata and logging
