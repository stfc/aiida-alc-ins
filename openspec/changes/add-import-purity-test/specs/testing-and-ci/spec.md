## ADDED Requirements

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

#### Scenario: The contract is checked where AiiDA is absent

- **WHEN** the independence check runs
- **THEN** it evaluates the operations in an interpreter in which AiiDA has not
  already been imported and no AiiDA configuration location has been supplied

#### Scenario: An import of AiiDA anywhere in the chain is detected

- **WHEN** any module reachable from the operations' import chain begins to
  import AiiDA
- **THEN** the suite fails, identifying that AiiDA was loaded

#### Scenario: The package's own modules are not mistaken for AiiDA

- **WHEN** the check inspects which modules were loaded
- **THEN** modules belonging to this package are not reported as AiiDA, and the
  check passes while the contract holds

#### Scenario: Calling an operation does not introduce a dependency on AiiDA

- **WHEN** an operation is called in that same interpreter
- **THEN** it returns its result, and no AiiDA module has been loaded as a
  consequence
