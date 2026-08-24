# documentation Specification

## Purpose

Provide documentation that works as an exemplar for the `aiida-pythonjob`
execution model: an accurate API reference, workflow interfaces taken from the
live process specifications, and worked examples that are executed and verified
whenever the documentation is built.
## Requirements
### Requirement: API reference is generated from the source

The documentation SHALL include an API reference generated automatically from the
package source, so it cannot drift from the code as modules are added or changed.

#### Scenario: Modules appear in the reference without manual listing

- **WHEN** the documentation is built
- **THEN** the package's modules, classes and functions appear in a generated API
  reference, with no per-module stub files maintained by hand

### Requirement: Workflow interfaces are documented from their runtime spec

A WorkChain's interface is defined at runtime and is invisible to static analysis,
which would otherwise expose only its internal step methods. The documentation
SHALL therefore render workflow interfaces from the live process specification,
and SHALL keep the misleading static view out of the API reference. The workflow
documentation SHALL explicitly document the WorkChain exit codes defined by the
package (including exit code 400 `ERROR_SUB_PROCESS_FAILED`).

#### Scenario: A workflow page shows its real interface

- **WHEN** the documentation is built
- **THEN** each workflow's page lists its actual inputs, outputs, exit codes and outline

#### Scenario: Outline methods are not presented as the public interface

- **WHEN** the generated API reference is built
- **THEN** WorkChain classes are excluded from it, so their internal step methods
  are not shown in place of their interface

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

### Requirement: Building the documentation does not touch a real AiiDA installation

Because the build loads AiiDA profiles to render workflow specifications and to
execute examples, it SHALL use throwaway configuration and in-memory profiles, and
SHALL NOT read or modify a developer's real AiiDA installation.

#### Scenario: Building on a machine with a configured AiiDA

- **WHEN** the documentation is built on a machine with an existing AiiDA
  installation
- **THEN** that installation is neither read nor modified

#### Scenario: Building on a fresh machine

- **WHEN** the documentation is built in continuous integration with no AiiDA
  configuration present
- **THEN** the build creates its own ephemeral configuration and succeeds

### Requirement: The documentation build is clean and automated

The documentation SHALL build without warnings, SHALL be built automatically on
pull requests to catch breakage, and SHALL be publishable to a hosted site on
demand. The build environment SHALL provide the system tools needed to render
provenance graphs and to run the direct scheduler.

#### Scenario: A pull request builds the documentation

- **WHEN** a pull request is opened
- **THEN** continuous integration builds the documentation, including executing the
  examples, and reports failure on any error

#### Scenario: Publishing is deliberate

- **WHEN** a maintainer triggers the documentation workflow manually
- **THEN** the built site is deployed to the hosted documentation site

#### Scenario: Warnings are treated as defects

- **WHEN** the documentation is built
- **THEN** it completes without Sphinx warnings

### Requirement: The prototype status and AI authorship are disclosed

The project is a prototype produced largely through agentic coding. Both the
repository README and the documentation landing page SHALL say so prominently, so
that readers do not mistake it for production-ready software and know to review
the code before relying on it.

#### Scenario: A reader arrives at the documentation

- **WHEN** the documentation landing page is viewed
- **THEN** a prominent notice states that the project is a prototype built with
  agentic coding and should be reviewed before use

#### Scenario: A reader arrives at the repository

- **WHEN** the README is viewed
- **THEN** it carries the same disclosure

