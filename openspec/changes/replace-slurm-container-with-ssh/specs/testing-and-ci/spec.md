## ADDED Requirements

### Requirement: Containerized integration tests execute remote jobs over SSH

The test suite SHALL provide an integration test setup that launches an ephemeral container running an SSH daemon and HyperQueue service, configures an AiiDA `Computer` using `core.ssh` transport and `hyperqueue` scheduler, and executes end-to-end AiiDA workflows or `PythonJob` tasks against the containerized queue in an interpreter where AiiDA is not installed.

#### Scenario: Running a workflow on a containerized computer

- **WHEN** an integration test is run with an available container runtime
- **THEN** the test submits a workflow to the containerized queue over SSH, polls to completion, and receives valid results and provenance links

#### Scenario: SSH connection is bound strictly to local loopback

- **WHEN** the container is started by the test fixture
- **THEN** its SSH port is published exclusively on `127.0.0.1` at a dynamically assigned local port

#### Scenario: Authentication uses dynamic session keys

- **WHEN** the container is launched for a test session
- **THEN** an ephemeral SSH keypair is generated and injected at runtime, and no static private key is read from version control

#### Scenario: Remote execution takes place where AiiDA is absent

- **WHEN** a job executes in the remote container environment
- **THEN** the job completes successfully and AiiDA is not importable in the remote interpreter

### Requirement: Containerized test fixtures are safe for parallel test execution

The test suite SHALL support parallel test execution via `pytest-xdist` without running multiple redundant container instances or encountering race conditions during image builds or port assignments. A single container instance SHALL be shared across all parallel test worker processes, and non-containerized unit tests SHALL execute without waiting for container startup.

#### Scenario: Running tests in parallel with pytest-xdist

- **WHEN** the test suite is executed in parallel across multiple worker processes with `pytest-xdist`
- **THEN** exactly one container instance is launched, parallel workers share access to it, and all containerized tests complete without port or build collision

#### Scenario: Unit tests execute without waiting for container initialization

- **WHEN** a parallel test run begins that contains both unit tests and containerized integration tests
- **THEN** non-containerized unit tests execute immediately without waiting for container image building or startup

## REMOVED Requirements

### Requirement: Containerized Slurm integration tests execute remote jobs

**Reason**: Slurm is removed from automated integration testing in favor of a lightweight HyperQueue scheduler and SSH transport; Slurm coverage moves to a human-run tutorial.
**Migration**: Run containerized integration tests against the SSH and HyperQueue test computer.
