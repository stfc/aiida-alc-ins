# plugin-packaging Specification

## Purpose

Make the plugin installable and discoverable as a well-behaved member of the
AiiDA plugin ecosystem, co-existing with other plugins in a shared environment
without imposing avoidable dependency conflicts.
## Requirements
### Requirement: Plugin classes are discoverable through AiiDA entry points

The package SHALL register its data types under the `aiida.data` entry-point group
and its workflows under `aiida.workflows`, using the `alc_ins` prefix, so
that AiiDA users can load them through the standard plugin factories rather than
by direct import. The registered set SHALL cover every data type and workflow
intended for users to load, so introducing one is a modification to this
requirement and to the scenarios below.

Where two workflows perform the same calculation from different starting data,
their entry-point names SHALL distinguish them by that starting data, since the
result alone does not.

#### Scenario: Data classes load through the data factory

- **WHEN** `alc_ins.crystal`, `alc_ins.force_constants` or
  `alc_ins.qpoint_phonon_modes` is requested from AiiDA's data factory
- **THEN** the corresponding `EuphonicCrystalData`, `ForceConstantsData` or
  `QpointPhononModesData` class is returned

#### Scenario: Workflows load through the workflow factory

- **WHEN** `alc_ins.force_constants`, `alc_ins.dispersion`,
  `alc_ins.dos`, `alc_ins.tosca_from_modes` or
  `alc_ins.tosca_from_force_constants` is requested from AiiDA's workflow
  factory
- **THEN** the corresponding `ForceConstantsWorkChain`, `DispersionWorkChain`,
  `DosWorkChain`, `ToscaFromModesWorkChain` or `ToscaFromForceConstantsWorkChain`
  class is returned

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
avoidable conflicts. The package SHALL pin `abinslib~=0.2.0` from PyPI to match
the decoupled weighting API introduced in abinslib 0.2.

#### Scenario: Each dependency records its rationale

- **WHEN** the declared dependencies are reviewed
- **THEN** each carries a stated reason for its lower bound and for any upper cap
- **AND** `abinslib` is declared as `~=0.2.0` from PyPI

#### Scenario: A sibling's transitive constraint is not restated

- **WHEN** a dependency of this package imposes its own stricter requirement on a
  shared dependency
- **THEN** this package does not restate that requirement, leaving the resolver to
  enforce it

### Requirement: The distribution installs as a standard Python package

The distribution SHALL be named `aiida-alc-ins` and provide the import
package `aiida_alc_ins` from a src layout, SHALL declare its supported
Python version range as Python 3.11 or greater (`>=3.11`), and SHALL be built by a PEP 517 backend consistent with the
project's uv-based workflow. The distribution SHALL carry the descriptive metadata
a package index displays: a description, licence, project links, authors and
classifiers, including its development status.

#### Scenario: Installing provides the import package

- **WHEN** the distribution `aiida-alc-ins` is installed
- **THEN** `aiida_alc_ins` is importable

#### Scenario: The Python version requirement is enforced

- **WHEN** installation is attempted on a Python outside the declared supported
  version range
- **THEN** the installation is rejected by the declared requirement

#### Scenario: The built distributions carry the package code

- **WHEN** the source distribution and the wheel are built
- **THEN** each contains the import package, and the wheel's entry points are the
  ones the package declares

### Requirement: The package reports its version from its distribution metadata

The package SHALL expose `aiida_alc_ins.__version__`, equal to the version
of the installed distribution. The version SHALL be written in one place only, so
that the value reported by the package, the distribution metadata and the
documentation cannot disagree. Because AiiDA records a plugin's version in the
provenance of every process only when its top-level module defines `__version__`,
runs of this package's workflows SHALL record the package version.

#### Scenario: The reported version matches the installed distribution

- **WHEN** `aiida_alc_ins.__version__` is read in an environment where the
  distribution is installed
- **THEN** it equals the version in the installed distribution's metadata

#### Scenario: The reported version matches the declared version

- **WHEN** `aiida_alc_ins.__version__` is read in an environment where the
  distribution is installed from the current source
- **THEN** it equals the version declared in the project's configuration

#### Scenario: Provenance records the plugin version

- **WHEN** a workflow from this package runs
- **THEN** its process node records the package version as its plugin version

#### Scenario: The documentation shows the same version

- **WHEN** the documentation is built
- **THEN** the release number it displays equals the installed distribution's
  version
