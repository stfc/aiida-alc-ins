# Spec Delta: plugin-packaging

## MODIFIED Requirements

### Requirement: Euphonic installs from PyPI wherever wheels are published

Euphonic SHALL be resolved directly from PyPI across all supported development and deployment platforms (including x86-64 and aarch64 Linux). The project SHALL NOT require or configure a local wheel directory or platform-specific wheel staging workarounds.

#### Scenario: Resolution on a platform with published wheels

- **WHEN** dependencies are resolved on x86-64 Linux with no local wheel present
- **THEN** Euphonic is installed from PyPI

#### Scenario: Resolution on aarch64 with a supplied wheel

- **WHEN** dependencies are resolved on aarch64 Linux
- **THEN** Euphonic is installed directly from PyPI without requiring a locally supplied wheel directory

#### Scenario: The requirement for a local wheel is documented

- **WHEN** a developer sets up the project on any supported platform
- **THEN** documentation does not require obtaining or placing local wheel files manually
