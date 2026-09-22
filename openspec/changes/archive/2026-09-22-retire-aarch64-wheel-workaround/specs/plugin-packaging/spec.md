# Spec Delta: plugin-packaging

## REMOVED Requirements

### Requirement: Euphonic installs from PyPI wherever wheels are published

The requirement documented a temporary local-wheel workaround for aarch64 Linux.
With official aarch64 Euphonic 2.x wheels now published on PyPI, Euphonic
resolves from PyPI on all supported platforms like every other dependency, and
the requirement no longer encodes a contract unique to this project.
