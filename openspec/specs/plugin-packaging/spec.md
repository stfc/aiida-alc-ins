# plugin-packaging Specification

## Purpose

Make the plugin installable and discoverable as a well-behaved member of the
AiiDA plugin ecosystem, co-existing with other plugins in a shared environment
without imposing avoidable dependency conflicts.
## Requirements
### Requirement: Plugin classes are discoverable through AiiDA entry points

The package SHALL register its data types under the `aiida.data` entry-point group
and its workflows under `aiida.workflows`, using the `pythonjob_ins` prefix, so
that AiiDA users can load them through the standard plugin factories rather than
by direct import. The registered set SHALL cover every data type and workflow
intended for users to load, so introducing one is a modification to this
requirement and to the scenarios below.

Where two workflows perform the same calculation from different starting data,
their entry-point names SHALL distinguish them by that starting data, since the
result alone does not.

#### Scenario: Data classes load through the data factory

- **WHEN** `pythonjob_ins.crystal`, `pythonjob_ins.force_constants` or
  `pythonjob_ins.qpoint_phonon_modes` is requested from AiiDA's data factory
- **THEN** the corresponding `EuphonicCrystalData`, `ForceConstantsData` or
  `QpointPhononModesData` class is returned

#### Scenario: Workflows load through the workflow factory

- **WHEN** `pythonjob_ins.dispersion`, `pythonjob_ins.dos`,
  `pythonjob_ins.tosca_from_modes` or `pythonjob_ins.tosca_from_force_constants`
  is requested from AiiDA's workflow factory
- **THEN** the corresponding `DispersionWorkChain`, `DosWorkChain`,
  `ToscaFromModesWorkChain` or `ToscaFromForceConstantsWorkChain` class is
  returned

#### Scenario: Every declared entry point resolves to its class

- **WHEN** the installed AiiDA plugins are listed for the `aiida.data` and
  `aiida.workflows` groups
- **THEN** every entry point this package declares is listed, and each loads the
  class it names

### Requirement: Serializer registry keys track the classes they name

The mapping from scientific object types to the AiiDA nodes that store them is
keyed by the type's import path, resolved as text at run time. A key that no
longer matches its type does not raise: the object silently falls back to generic
storage and a workflow receives a node of the wrong type.

Registry keys SHALL therefore be derived from the classes themselves rather than
written out by hand, so that a key follows its class if the class is relocated
upstream. Every registered key SHALL be verifiable as naming a real, importable
class, so that a relocation the package does not otherwise notice is reported.

#### Scenario: Every registry key names an importable class

- **WHEN** the registered mappings are inspected
- **THEN** every key resolves to a class that can be imported

#### Scenario: A registered type is stored as its intended node type

- **WHEN** a job returns an object of a registered type
- **THEN** the resulting node is of the type the registry names for it, not a
  generic fallback

### Requirement: Entry-point names do not collide with serializer discovery

`aiida-pythonjob` inspects `aiida.data` entry-point names when building its
serializer registry. This package's entry-point names SHALL be chosen so they are
not interpreted as serializer registrations, keeping one clean entry point per
class and avoiding duplicate-key clashes at import time.

#### Scenario: The serializer registry builds cleanly

- **WHEN** `aiida-pythonjob` builds its serializer registry in an environment where
  this package is installed
- **THEN** the registry is constructed without a duplicate-key error
- **AND** this package's entry points are not registered as serializers

### Requirement: Dependency bounds are justified by this package's own usage

Dependency constraints SHALL be derived from the APIs this package actually uses,
not copied from the constraints of sibling dependencies. Upper caps SHALL be
applied only where individually justified, because a resolver intersects the
requirements of every co-installed plugin and needlessly narrow pins cause
avoidable conflicts.

#### Scenario: Each dependency records its rationale

- **WHEN** the declared dependencies are reviewed
- **THEN** each carries a stated reason for its lower bound and for any upper cap

#### Scenario: A sibling's transitive constraint is not restated

- **WHEN** a dependency of this package imposes its own stricter requirement on a
  shared dependency
- **THEN** this package does not restate that requirement, leaving the resolver to
  enforce it

### Requirement: The distribution installs as a standard Python package

The distribution SHALL be named `aiida-pythonjob-ins` and provide the import
package `aiida_pythonjob_ins` from a src layout, SHALL declare its supported
Python version range as Python 3.11 or greater (`>=3.11`), and SHALL be built by a PEP 517 backend consistent with the
project's uv-based workflow.

#### Scenario: Installing provides the import package

- **WHEN** the distribution `aiida-pythonjob-ins` is installed
- **THEN** `aiida_pythonjob_ins` is importable

#### Scenario: The Python version requirement is enforced

- **WHEN** installation is attempted on a Python outside the declared supported
  version range
- **THEN** the installation is rejected by the declared requirement

### Requirement: Euphonic installs from PyPI wherever wheels are published

Euphonic SHALL be resolved from PyPI on platforms where a compatible wheel is
published. On platforms without one, currently aarch64 Linux, a locally supplied
wheel SHALL be used instead, without altering the declared dependency or
affecting other platforms. The workaround SHALL be removable without any other
change once upstream wheels become available.

#### Scenario: Resolution on a platform with published wheels

- **WHEN** dependencies are resolved on x86-64 Linux with no local wheel present
- **THEN** Euphonic is installed from PyPI

#### Scenario: Resolution on aarch64 with a supplied wheel

- **WHEN** dependencies are resolved on aarch64 Linux and a compatible Euphonic
  wheel has been placed in the project's local wheel directory
- **THEN** that wheel is used to satisfy the Euphonic requirement

#### Scenario: The requirement for a local wheel is documented

- **WHEN** a developer sets up the project on a platform with no published wheel
- **THEN** the README tells them to obtain and place the wheel themselves, since it
  is deliberately not committed to the repository

