# testing-and-ci Specification

## Purpose

Keep the test suite runnable anywhere without external services or manual setup,
and guarantee that running it never reads or modifies a developer's real AiiDA
installation.
## Requirements
### Requirement: The test session is hermetic with respect to AiiDA configuration

A test run SHALL use an ephemeral AiiDA configuration directory created for that
session and removed afterwards. It SHALL NOT read or modify a developer's real
AiiDA configuration, profiles or stored data, and SHALL behave identically whether
or not such an installation exists.

#### Scenario: Running with no existing AiiDA installation

- **WHEN** the suite is run on a machine that has never had AiiDA configured
- **THEN** collection and execution succeed, using a configuration created in a
  temporary directory

#### Scenario: Running alongside a developer's live installation

- **WHEN** the suite is run on a machine with an existing AiiDA configuration
- **THEN** that configuration is neither read nor modified, and the results are the
  same as on a fresh machine

#### Scenario: Configuration is established before AiiDA is imported

- **WHEN** a test module imports this package during collection, which causes
  `aiida-pythonjob` to read AiiDA configuration at import time
- **THEN** the ephemeral configuration is already in place, so collection does not
  fail with a missing-configuration error

#### Scenario: The temporary configuration is cleaned up

- **WHEN** the test session ends
- **THEN** the ephemeral configuration directory is removed

### Requirement: Tests require no external services

The suite SHALL run using AiiDA's official pytest fixtures with temporary,
throwaway profiles on a file-backed store. It SHALL NOT require PostgreSQL, a
message broker, or a running AiiDA daemon.

#### Scenario: A full run on a bare machine

- **WHEN** the suite is run in an environment with only the project's declared
  dependencies installed
- **THEN** every test runs to completion without any database or broker service

### Requirement: Job tests execute in the active environment

Tests that launch jobs SHALL use the interpreter running the tests as their
execution code, so the job environment always contains the package version under
test and its dependencies.

#### Scenario: The test code points at the running interpreter

- **WHEN** a test needs a code to run a job on localhost
- **THEN** an installed code is provided whose executable is the current
  interpreter and whose default plugin is the PythonJob calculation plugin

### Requirement: Scientific results are verified by equivalence, not golden values

Tests of scientific behaviour SHALL compare the AiiDA-wrapped result against a
direct call to the underlying public Euphonic API, rather than against
hard-coded reference numbers, with tolerances wide enough to absorb eigensolver
noise between processes but narrow enough to catch real regressions.

#### Scenario: A wrapped calculation is checked against a direct one

- **WHEN** a phonon calculation is run both through AiiDA and directly
- **THEN** the two results are compared numerically within a stated tolerance, and
  no reference frequency values appear in the test

### Requirement: The environment provides the process tools the scheduler needs

Job tests run through AiiDA's direct scheduler, which tracks running jobs by
polling the system process table with `ps`, using BSD-style options so that
processes with no controlling terminal are still listed. Any environment running
the suite or building the documentation SHALL provide a `ps` supporting that
usage. This SHALL be a declared environment prerequisite, not worked around in
code.

#### Scenario: A minimal environment lacks the tool

- **WHEN** the suite is run where `ps` is absent or does not support these options
- **THEN** the shortfall is treated as an unmet environment prerequisite, and the
  code neither detects nor compensates for it

#### Scenario: Prerequisites are discoverable

- **WHEN** a developer prepares an environment in which to run the suite or build
  the documentation
- **THEN** the documented prerequisites state this requirement alongside the other
  system-level ones

### Requirement: Continuous integration runs the suite on every change

The project SHALL run its test suite and static analysis (linting and code formatting checks via `ruff`) automatically on pushes to the main branch
and on pull requests, across a matrix of supported Python versions (3.11, 3.12, 3.13, and 3.14), installing dependencies from
the project's declared configuration. Coverage SHALL include the primary target
platform, x86-64 Linux; extending it to further platforms SHALL NOT require any
change to this requirement.

#### Scenario: A pull request is opened

- **WHEN** a pull request is opened against the repository
- **THEN** continuous integration installs the project, verifies code formatting and linting rules with ruff, and runs the test suite across the Python version matrix,
  reporting failure if any step fails

#### Scenario: The primary target platform is covered

- **WHEN** the continuous integration configuration is inspected
- **THEN** it runs the suite on x86-64 Linux across Python versions 3.11, 3.12, 3.13, and 3.14

### Requirement: Plugin registration is verified through the plugin factories

The suite SHALL verify that every class this package registers as an AiiDA plugin
is returned by the corresponding plugin factory when requested by its documented
entry-point name. Coverage SHALL be expressed per registered class, so that a
newly registered class without a corresponding case is a visible omission. The
verification SHALL exercise registration as installed in the environment under
test, rather than importing the classes directly.

#### Scenario: Each registered data type loads from the data factory

- **WHEN** a registered data type's documented entry-point name is requested from
  AiiDA's data factory
- **THEN** the factory returns that class

#### Scenario: Each registered workflow loads from the workflow factory

- **WHEN** a registered workflow's documented entry-point name is requested from
  AiiDA's workflow factory
- **THEN** the factory returns that class

#### Scenario: A registration that is removed or renamed is detected

- **WHEN** an entry-point declaration is removed, or its name changed, while the
  class itself remains importable
- **THEN** the suite fails

#### Scenario: Verification needs no stored data

- **WHEN** the registration checks run
- **THEN** they resolve the plugins without storing a node, submitting a job or
  requiring any service beyond the test session's own configuration

### Requirement: Containerized Slurm integration tests execute remote jobs

The test suite SHALL provide an integration test setup that launches an ephemeral Slurm container running an SSH daemon, configures an AiiDA `Computer` using `core.ssh` transport and `core.slurm` scheduler, and executes end-to-end AiiDA workflows or `PythonJob` tasks against the containerized Slurm queue.

#### Scenario: Running a workflow on a containerized Slurm computer

- **WHEN** an integration test is run with an available container runtime
- **THEN** the test submits a workflow to the containerized Slurm queue over SSH, polls to completion, and receives valid results and provenance links

#### Scenario: SSH connection is bound strictly to local loopback

- **WHEN** the Slurm container is started by the test fixture
- **THEN** its SSH port is published exclusively on `127.0.0.1` at a dynamically assigned local port

### Requirement: Integration tests auto-skip when container runtimes are unavailable

The suite SHALL auto-detect whether a supported container engine (`podman` or `docker`) is installed and operational. If no container engine is available, or if containerized tests are explicitly deselected via Pytest marker filtering, containerized tests SHALL be skipped cleanly without causing test suite failure.

#### Scenario: Running tests when no container engine is installed

- **WHEN** the test suite runs in an environment lacking `podman` and `docker`
- **THEN** containerized integration tests are skipped with a clear skip message

#### Scenario: Running tests with containerized marker deselection

- **WHEN** the test suite is executed with `pytest -m "not containerized"`
- **THEN** containerized integration tests are deselected during collection

### Requirement: Containerized integration tests are registered with a Pytest marker

The project SHALL register the `containerized` Pytest marker in `pyproject.toml` so that developers can selectively run or deselect containerized integration tests using standard `pytest` marker selection options.

#### Scenario: Running only containerized tests

- **WHEN** the test suite is executed with `pytest -m containerized`
- **THEN** only tests marked as `containerized` are executed

