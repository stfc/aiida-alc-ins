## Purpose

Define how a release of the distribution reaches the package index: what starts a
release, what must be true before anything is uploaded, and what credentials the
process may hold. Releases are built and published by CI, not from a maintainer's
machine.

## ADDED Requirements

### Requirement: Releases are published by CI without stored credentials

The distribution SHALL be published to the package index from a CI workflow that
authenticates through the index's trusted-publishing mechanism, and SHALL NOT
require a long-lived API token stored as a repository secret. Publication to the
production index SHALL be bound to a named deployment environment, so that
repository settings can require approval before it proceeds.

#### Scenario: A release is published without an API token

- **WHEN** a release workflow run publishes the distribution
- **THEN** it authenticates with a short-lived credential issued to that run
- **AND** no API token is read from repository secrets

#### Scenario: Production publication is tied to its environment

- **WHEN** a run publishes to the production index
- **THEN** the publishing step runs in the deployment environment reserved for
  the production index

### Requirement: A release starts from a published release or a manual dispatch

The release workflow SHALL start when a GitHub release is published, which
publishes to the production index, and on manual dispatch, where the maintainer
chooses the git ref and whether the target is the production index or the test
index. A manual dispatch SHALL NOT need a GitHub release to exist. No other event,
including a push or a pull request, SHALL start a publication.

#### Scenario: Publishing a GitHub release publishes to the production index

- **WHEN** a GitHub release is published for a tag
- **THEN** the workflow builds that tag and publishes it to the production index

#### Scenario: A manual dispatch can target the test index

- **WHEN** a maintainer dispatches the workflow for a ref with the test index as
  the target
- **THEN** the build of that ref is published to the test index only
- **AND** the production index is not contacted

#### Scenario: Ordinary development never publishes

- **WHEN** a commit is pushed or a pull request is opened or updated
- **THEN** no distribution is uploaded to any index

### Requirement: The released version must match the declared version

For a published GitHub release, the version named by the release's tag SHALL equal
the version declared by the distribution at that tag. A mismatch SHALL fail the
run before any upload, leaving the index unchanged.

#### Scenario: A matching tag publishes

- **WHEN** a release is published for a tag whose version equals the declared
  version of the distribution at that tag
- **THEN** the run proceeds to verification and publication

#### Scenario: A mismatched tag stops the run before upload

- **WHEN** a release is published for a tag whose version differs from the
  declared version at that tag
- **THEN** the run fails
- **AND** nothing is uploaded to any index

### Requirement: Built distributions are verified before upload

The workflow SHALL build both a source distribution and a wheel and SHALL verify
them before any upload. Verification SHALL check that the distribution metadata is
well formed, and that the wheel installs into a clean environment in which every
entry point the package declares can be loaded. A failure SHALL stop the run
before any upload.

#### Scenario: A wheel with a missing entry-point target is not published

- **WHEN** the built wheel declares an entry point whose target cannot be imported
  after installation into a clean environment
- **THEN** verification fails
- **AND** nothing is uploaded

#### Scenario: A wheel without the package code is not published

- **WHEN** the built wheel does not provide the import package
- **THEN** verification fails
- **AND** nothing is uploaded

#### Scenario: Both distribution formats are published together

- **WHEN** verification succeeds
- **THEN** the source distribution and the wheel built from the same commit are
  both uploaded

### Requirement: Building is separated from publishing

The step that holds publishing credentials SHALL NOT build the distributions. It
SHALL upload exactly the files produced and verified by an earlier, credential-free
step, so that project code and build tooling never run with the ability to
publish.

#### Scenario: The publishing step uploads the verified files unchanged

- **WHEN** the publishing step runs
- **THEN** the files it uploads are those the verification step accepted
- **AND** it runs no project build

### Requirement: The release procedure is documented for maintainers

The repository's contributor documentation SHALL describe how to make a release:
the one-off setup at the index and in the repository, the order of steps, how to
rehearse on the test index, and the version-number convention between releases.

#### Scenario: A maintainer can release from the documentation alone

- **WHEN** a maintainer follows the documented procedure
- **THEN** it covers configuring the trusted publisher, setting the release
  version, publishing, and setting the next development version afterwards
