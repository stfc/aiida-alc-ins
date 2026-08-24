## MODIFIED Requirements

### Requirement: Worked examples are executed when the documentation is built

The documentation SHALL include runnable examples that execute real workflows
during the build, so a broken example fails the build rather than silently
misleading readers. Each example SHALL present both its scientific result and the
provenance graph that produced it, and SHALL be downloadable as a notebook. Worked
examples and project README examples SHALL demonstrate loading custom data nodes
and workflows through AiiDA's standard plugin factories (`DataFactory` and `WorkflowFactory`)
as the primary pattern, noting that direct class imports are also supported.

Where an example's sample material is a poor illustration of the calculation being
demonstrated — scientifically valid but unrepresentative of how the method is
used — the example SHALL say so on the page, rather than leaving the reader to
infer that it is typical.

#### Scenario: Examples cover the supported inputs and both workflows

- **WHEN** the example gallery is built
- **THEN** it includes a band structure from CASTEP input, a density of states from
  CASTEP input, and both quantities from Phonopy input

#### Scenario: Examples cover the spectrometer workflows

- **WHEN** the example gallery is built
- **THEN** it also includes a spectrometer spectrum computed from prepared phonon
  modes, and one computed from force constants

#### Scenario: Each example shows its provenance

- **WHEN** an example runs during the build
- **THEN** it renders the scientific result as a figure and the resulting AiiDA
  provenance graph as a second figure

#### Scenario: Examples use bundled sample data

- **WHEN** an example needs input data
- **THEN** it locates the sample files bundled in the repository at runtime, rather
  than downloading them or requiring the reader to supply them

#### Scenario: Examples use plugin factories for loading classes

- **WHEN** an example or README snippet loads a registered data type or workflow
- **THEN** it demonstrates loading via `DataFactory` or `WorkflowFactory`, with a brief note that direct class imports are also supported

#### Scenario: An unrepresentative sample is declared as such

- **WHEN** an example demonstrates a calculation on a material that is not
  representative of that calculation's usual application
- **THEN** the page states that the result is a demonstration of the method rather
  than a typical measurement

## ADDED Requirements

### Requirement: An example demonstrating reuse proves that reuse occurred

Where an example is included to show that repeating part of a calculation can
reuse previously computed results, it SHALL enable that reuse explicitly and SHALL
assert that it took place, so that the demonstration fails the documentation build
if the reuse silently stops working.

#### Scenario: Reuse is enabled and verified

- **WHEN** an example varies a cheap parameter and re-runs a workflow to show that
  the expensive step is not repeated
- **THEN** the example enables result reuse explicitly rather than relying on the
  ambient configuration
- **AND** it asserts that the expensive step's result was taken from the cache, so
  that a failure of reuse breaks the build
