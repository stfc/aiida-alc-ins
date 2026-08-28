## Purpose

Enables aiida-pythonjob-ins to run on Python 3.10 environments, allowing downstream users with Python 3.10 constraints to use the package.

## ADDED Requirements

### Requirement: Python 3.10 runtime support

The package SHALL be installable and runnable on Python 3.10.

#### Scenario: Install on Python 3.10
- **WHEN** a user installs aiida-pythonjob-ins on Python 3.10
- **THEN** the package and all dependencies resolve successfully

#### Scenario: Import on Python 3.10
- **WHEN** a user imports aiida_pythonjob_ins on Python 3.10
- **THEN** the package imports without errors

### Requirement: abinslib dependency with Python-version-conditional sources

The abinslib dependency SHALL be resolved from different sources depending on Python version.

#### Scenario: abinslib from git on Python 3.10
- **WHEN** aiida-pythonjob-ins is installed on Python 3.10
- **THEN** abinslib is installed from the `py310-0.1` branch at `github.com/ISISNeutronMuon/abINS_lib`

#### Scenario: abinslib from PyPI on Python 3.11+
- **WHEN** aiida-pythonjob-ins is installed on Python 3.11 or later
- **THEN** abinslib is installed from PyPI with version constraint `0.1.*`

### Requirement: Backported typing compatibility

The package SHALL use `typing_extensions.Self` for type annotations to support Python 3.10.

#### Scenario: Self import on Python 3.10
- **WHEN** the package imports `Self` from `typing_extensions`
- **THEN** the import succeeds on Python 3.10

#### Scenario: Self import on Python 3.11+
- **WHEN** the package imports `Self` from `typing_extensions`
- **THEN** the import succeeds on Python 3.11+ (using the backport)

### Requirement: CI testing on Python 3.10

The CI test matrix SHALL include Python 3.10 to verify compatibility.

#### Scenario: CI runs tests on Python 3.10
- **WHEN** CI runs the test suite
- **THEN** tests execute on Python 3.10, 3.11, and 3.14
