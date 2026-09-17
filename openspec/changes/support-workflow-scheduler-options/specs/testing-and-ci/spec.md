# Spec Delta

## MODIFIED Requirements

### Requirement: Containerized integration tests execute remote jobs over SSH

The test suite SHALL provide an integration test setup that launches an ephemeral container running an SSH daemon and HyperQueue service, configures an AiiDA `Computer` using `core.ssh` transport and `hyperqueue` scheduler, and executes end-to-end AiiDA workflows or `PythonJob` tasks against the containerized queue in an interpreter where AiiDA is not installed.

Remote job and workflow submissions executed against the containerized HyperQueue scheduler
SHALL declare scheduler resources using task-based parameters (`num_cpus`), and the test suite
configuration SHALL execute without filtering or ignoring HyperQueue scheduler deprecation warnings.

#### Scenario: Running a workflow on a containerized computer

- **WHEN** an integration test is run with an available container runtime
- **THEN** the test submits a workflow to the containerized queue over SSH, polls to completion, and receives valid results and provenance links

#### Scenario: Remote jobs and workflows declare task-based scheduler resources

- **WHEN** an integration test submits a `PythonJob` or workflow to the HyperQueue container
- **THEN** the submission specifies CPU count resources directly rather than relying on machine-count fallback
- **AND** execution completes without raising scheduler deprecation warnings

#### Scenario: HyperQueue deprecation warnings are not suppressed in test configuration

- **WHEN** the test configuration is inspected
- **THEN** no warning filter suppresses `AiiDAHypereQueueDeprecationWarning`

#### Scenario: SSH connection is bound strictly to local loopback

- **WHEN** the container is started by the test fixture
- **THEN** its SSH port is published exclusively on `127.0.0.1` at a dynamically assigned local port

#### Scenario: Authentication uses dynamic session keys

- **WHEN** the container is launched for a test session
- **THEN** an ephemeral SSH keypair is generated via high-level SSH primitives (`SSHKeyPair`) exposing explicit private and public key paths, injected into `/home/ubuntu/.ssh/authorized_keys` at runtime, and no static private key is read from version control

#### Scenario: Remote execution takes place where AiiDA is absent

- **WHEN** a job executes in the remote container environment
- **THEN** the job completes successfully and AiiDA is not importable in the remote interpreter
