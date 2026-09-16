## MODIFIED Requirements

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

## ADDED Requirements

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
