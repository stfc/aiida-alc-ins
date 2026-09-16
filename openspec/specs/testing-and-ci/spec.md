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
test and its dependencies. This SHALL be the default. A test whose stated purpose
is to exercise execution outside the test session's own environment MAY direct its
code at another interpreter; where it does, the contents of that environment SHALL
derive from the project's declared configuration rather than from a separately
maintained list of packages.

#### Scenario: The test code points at the running interpreter

- **WHEN** a test needs a code to run a job on localhost
- **THEN** an installed code is provided whose executable is the current
  interpreter and whose default plugin is the PythonJob calculation plugin

#### Scenario: A test deliberately targets a different environment

- **WHEN** a test exists to verify behaviour that cannot be observed in the test
  session's own environment
- **THEN** it may use an interpreter other than the running one, and the packages
  present there follow from the project's declared dependencies

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

### Requirement: The containerized test environment derives its dependencies from the project's declared configuration

The environment in which containerized integration tests execute remote jobs
SHALL obtain its dependency versions from the project's declared runtime
dependencies. It SHALL NOT carry a second, independently maintained statement
of those versions, because two statements of the same fact can disagree and
nothing would detect that they had.

A change to the declared dependencies SHALL take effect in that environment on
the next run of the containerized tests, with no accompanying edit elsewhere
and no manual intervention to discard a previously built environment.

#### Scenario: A declared dependency constraint is changed

- **WHEN** a runtime dependency's declared version constraint is changed, and
  the containerized tests are then run on a machine that had already built the
  environment under the previous constraint
- **THEN** the environment the remote jobs execute in holds a version
  satisfying the new constraint

#### Scenario: The declared dependencies are the only place a version is stated

- **WHEN** the containerized test environment's definition is inspected for the
  versions of the project's runtime dependencies
- **THEN** no version or version constraint for any of them is stated there,
  each being taken from the project's declared configuration instead

#### Scenario: A job function importing a changed dependency runs remotely

- **WHEN** a job function is shipped to the containerized environment by module
  reference, and its import chain uses an interface introduced by a change to
  the project's declared dependencies
- **THEN** the function is imported and executed successfully, rather than
  failing to import

#### Scenario: An environment-only change is not silently ignored

- **WHEN** the declared dependencies change but nothing else about the
  containerized test setup does
- **THEN** the previously built environment is not reused unchanged

### Requirement: AiiDA independence is verified out of process

The suite SHALL verify the operations' independence from AiiDA in a separate
interpreter that has neither imported AiiDA nor been given an AiiDA
configuration location, so the result reflects only what importing and calling
the operations causes. An in-session check SHALL NOT be treated as satisfying
this requirement, because the test session imports and configures AiiDA before
any test runs and would report success regardless of the operations' own
imports.

The check SHALL distinguish AiiDA itself from distributions whose names merely
begin with the same letters, so that this package's own modules are not mistaken
for AiiDA.

When the check fails, it SHALL report enough to locate the cause without
re-running anything: which AiiDA module was loaded, and the chain of imports
that led to it, identified by source location. Reporting only that AiiDA was
loaded SHALL NOT satisfy this requirement, because the import that breaks the
contract is typically several modules away from the operations themselves.

#### Scenario: The contract is checked where AiiDA is absent

- **WHEN** the independence check runs
- **THEN** it evaluates the operations in an interpreter in which AiiDA has not
  already been imported and no AiiDA configuration location has been supplied

#### Scenario: An import of AiiDA anywhere in the chain is detected

- **WHEN** any module reachable from the operations' import chain begins to
  import AiiDA
- **THEN** the suite fails, identifying that AiiDA was loaded

#### Scenario: A failure names the imports that led to AiiDA

- **WHEN** the check fails because a module several hops from the operations
  imports AiiDA
- **THEN** the failure names the AiiDA module and the source location of each
  import between the operations and that module

#### Scenario: The check reports its own failures distinguishably

- **WHEN** the separate interpreter fails for a reason other than a contract
  violation
- **THEN** the suite fails with that interpreter's own error output, rather than
  reporting a contract violation

#### Scenario: The package's own modules are not mistaken for AiiDA

- **WHEN** the check inspects which modules were loaded
- **THEN** modules belonging to this package are not reported as AiiDA, and the
  check passes while the contract holds

#### Scenario: Calling an operation does not introduce a dependency on AiiDA

- **WHEN** an operation is called in that same interpreter
- **THEN** it returns its result, and no AiiDA module has been loaded as a
  consequence

### Requirement: By-reference execution is verified where AiiDA is absent

The suite SHALL verify that a job function shipped by module reference executes
successfully in an interpreter other than the one running the tests, in which
AiiDA is not importable. Pointing the execution code at the test session's own
interpreter SHALL NOT satisfy this requirement, because there the module
reference resolves for reasons that do not hold on a compute node.

The environment used SHALL be populated from the project's declared
configuration, so that no second list of remote dependencies exists to drift
from the first. Where the platform cannot provide such an environment, the
check SHALL be skipped rather than failed, in the same manner as other
environment-dependent tests in the suite.

#### Scenario: A job runs in an interpreter that has no AiiDA

- **WHEN** a job whose function is shipped by module reference is executed with
  its code pointing at an interpreter in which AiiDA is not importable
- **THEN** the job completes successfully and returns the same result as the
  equivalent job run in the test session's own environment

#### Scenario: A dependency missing from the distribution is detected

- **WHEN** the installed distribution omits a module that the job function's
  import chain requires at run time
- **THEN** the job fails in that interpreter and the suite reports the failure,
  rather than passing because the submitting environment supplied the module

#### Scenario: The remote environment follows the declared dependencies

- **WHEN** the project's declared dependencies change
- **THEN** the environment used for this check reflects that change without any
  further list of packages being edited

#### Scenario: The platform cannot build such an environment

- **WHEN** the suite runs where a separate interpreter environment cannot be
  created
- **THEN** the check is skipped with a clear message and the suite does not fail

### Requirement: Separate-interpreter tests are registered with a Pytest marker

The project SHALL register a Pytest marker identifying the tests that build and
run against a separate interpreter, so that developers can deselect them by
marker when their cost is not wanted. These tests SHALL be selected by default,
so that an ordinary run verifies the contract.

#### Scenario: Deselecting the separate-interpreter tests

- **WHEN** the suite is executed deselecting that marker
- **THEN** those tests are deselected during collection, no separate
  interpreter environment is built, and the rest of the suite runs unaffected

#### Scenario: An ordinary run includes them

- **WHEN** the suite is executed with no marker selection
- **THEN** the separate-interpreter tests are collected and run


