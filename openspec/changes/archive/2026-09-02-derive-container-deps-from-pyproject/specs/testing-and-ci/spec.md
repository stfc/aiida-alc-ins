## ADDED Requirements

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
