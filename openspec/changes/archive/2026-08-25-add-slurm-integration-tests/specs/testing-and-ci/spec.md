## ADDED Requirements

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
