# release-publishing Specification

## Purpose

Define how a release of the distribution reaches the package index (PyPI): what
starts an upload, what must be true before anything is uploaded, and what
credentials the process may hold. Uploads are built and made by CI, not from a
maintainer's machine. A GitHub release is a separate thing: it can exist without
anything being uploaded to PyPI.

## Requirements
### Requirement: Distributions are uploaded to PyPI by CI without stored credentials

The distribution SHALL be uploaded to the package index from a CI workflow that
authenticates through the index's trusted-publishing mechanism, and SHALL NOT
require a long-lived API token stored as a repository secret. The upload SHALL be
bound to a named deployment environment, so that repository settings can require
approval before it proceeds.

#### Scenario: An upload uses no API token

- **WHEN** a release workflow run uploads the distribution to PyPI
- **THEN** it authenticates with a short-lived credential issued to that run
- **AND** no API token is read from repository secrets

#### Scenario: The upload is tied to its environment

- **WHEN** a run uploads to the index
- **THEN** the uploading step runs in the deployment environment reserved for
  uploads

### Requirement: An upload starts from a GitHub release or a manual dispatch

The release workflow SHALL start when a GitHub release is published with a tag
beginning `v`, and on manual dispatch, where the maintainer chooses the git ref to
build. A dispatch SHALL NOT need a GitHub release. A GitHub release with any other
tag, a push and a pull request SHALL NOT start an upload to PyPI.

#### Scenario: A GitHub release with a version tag is uploaded to PyPI

- **WHEN** a GitHub release is published for a tag beginning `v`
- **THEN** the workflow builds that tag and uploads it to PyPI

#### Scenario: A GitHub release with another tag is not uploaded

- **WHEN** a GitHub release is published for a tag that does not begin with `v`
- **THEN** nothing is built or uploaded to PyPI, and the workflow run is skipped,
  not failed
- **AND** the GitHub release itself remains published

#### Scenario: A manual dispatch uploads a chosen ref without a GitHub release

- **WHEN** a maintainer dispatches the workflow for a ref that has no GitHub
  release
- **THEN** the workflow builds that ref and uploads the version it declares to
  PyPI

#### Scenario: Ordinary development never uploads

- **WHEN** a commit is pushed or a pull request is opened or updated
- **THEN** no distribution is uploaded to any index

### Requirement: The released version must match the declared version

For a published GitHub release, the version named by the release's tag SHALL equal
the version declared by the distribution at that tag. A mismatch SHALL fail the
run before any upload, leaving the index unchanged.

#### Scenario: A matching tag proceeds

- **WHEN** a release is published for a tag whose version equals the declared
  version of the distribution at that tag
- **THEN** the run proceeds to testing and upload

#### Scenario: A mismatched tag stops the run before upload

- **WHEN** a release is published for a tag whose version differs from the
  declared version at that tag
- **THEN** the run fails
- **AND** nothing is uploaded to any index

### Requirement: A development version is never uploaded to PyPI

Neither trigger SHALL upload a development version (a version that PEP 440 marks
as a development release, such as `0.2.0.dev0`), because the development version
is what the main branch carries between releases. Release candidates and
post-releases SHALL remain uploadable. A refusal SHALL fail the run before any
upload.

#### Scenario: A development version is refused

- **WHEN** the workflow is started for a ref whose declared version is a
  development release
- **THEN** the run fails
- **AND** nothing is uploaded to any index

#### Scenario: A release candidate is accepted

- **WHEN** the workflow is started for a ref whose declared version is a release
  candidate
- **THEN** the run is not refused on account of its version

### Requirement: Built distributions are tested before upload

The workflow SHALL build both a source distribution and a wheel and SHALL verify
that their metadata is well formed. It SHALL then install the wheel into a clean
environment, on the oldest supported Python, and run the project's tests against
that installation, excluding the tests that need a container runtime. The tests
SHALL exercise the installed wheel, not the source tree. A failure SHALL stop the
run before any upload.

#### Scenario: A failing test blocks the release

- **WHEN** a test fails against the installed wheel
- **THEN** the run fails
- **AND** nothing is uploaded

#### Scenario: A wheel without the package code is not uploaded

- **WHEN** the built wheel does not provide the import package
- **THEN** the tests fail
- **AND** nothing is uploaded

#### Scenario: The tests run against the installed wheel

- **WHEN** the tests run in the clean environment
- **THEN** the package they import is the one installed from the wheel, not one
  from the checked-out source tree

#### Scenario: Both distribution formats are uploaded together

- **WHEN** testing succeeds
- **THEN** the source distribution and the wheel built from the same commit are
  both uploaded

### Requirement: Building is separated from uploading

The step that holds the upload credentials SHALL NOT build the distributions. It
SHALL upload exactly the files produced and tested by earlier, credential-free
steps, so that project code and build tooling never run with the ability to
upload to PyPI.

#### Scenario: The uploading step uploads the tested files unchanged

- **WHEN** the uploading step runs
- **THEN** the files it uploads are those the testing step installed and tested
- **AND** it runs no project build

### Requirement: The release procedure is documented for maintainers

The repository's contributor documentation SHALL describe how to make a release:
the order of steps, the version-number convention between releases, and how to
correct a version that has been uploaded to PyPI in error.

#### Scenario: A maintainer can release from the documentation alone

- **WHEN** a maintainer follows the documented procedure
- **THEN** it covers setting the release version, publishing the GitHub release,
  and setting the next development version afterwards

#### Scenario: A maintainer can correct a bad release

- **WHEN** a version has been uploaded to PyPI with a defect
- **THEN** the documentation describes withdrawing it from the index and
  uploading a corrected version
