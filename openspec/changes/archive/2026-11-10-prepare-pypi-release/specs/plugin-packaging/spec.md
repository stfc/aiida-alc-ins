## MODIFIED Requirements

### Requirement: The distribution installs as a standard Python package

The distribution SHALL be named `aiida-alc-ins` and provide the import
package `aiida_pythonjob_ins` from a src layout, SHALL declare its supported
Python version range as Python 3.11 or greater (`>=3.11`), and SHALL be built by a PEP 517 backend consistent with the
project's uv-based workflow. The distribution SHALL carry the descriptive metadata
a package index displays: a description, licence, project links, authors and
classifiers, including its development status.

#### Scenario: Installing provides the import package

- **WHEN** the distribution `aiida-alc-ins` is installed
- **THEN** `aiida_pythonjob_ins` is importable

#### Scenario: The Python version requirement is enforced

- **WHEN** installation is attempted on a Python outside the declared supported
  version range
- **THEN** the installation is rejected by the declared requirement

#### Scenario: The built distributions carry the package code

- **WHEN** the source distribution and the wheel are built
- **THEN** each contains the import package, and the wheel's entry points are the
  ones the package declares

## ADDED Requirements

### Requirement: The package reports its version from its distribution metadata

The package SHALL expose `aiida_pythonjob_ins.__version__`, equal to the version
of the installed distribution. The version SHALL be written in one place only, so
that the value reported by the package, the distribution metadata and the
documentation cannot disagree. Because AiiDA records a plugin's version in the
provenance of every process only when its top-level module defines `__version__`,
runs of this package's workflows SHALL record the package version.

#### Scenario: The reported version matches the installed distribution

- **WHEN** `aiida_pythonjob_ins.__version__` is read in an environment where the
  distribution is installed
- **THEN** it equals the version in the installed distribution's metadata

#### Scenario: The reported version matches the declared version

- **WHEN** `aiida_pythonjob_ins.__version__` is read in an environment where the
  distribution is installed from the current source
- **THEN** it equals the version declared in the project's configuration

#### Scenario: Provenance records the plugin version

- **WHEN** a workflow from this package runs
- **THEN** its process node records the package version as its plugin version

#### Scenario: The documentation shows the same version

- **WHEN** the documentation is built
- **THEN** the release number it displays equals the installed distribution's
  version
