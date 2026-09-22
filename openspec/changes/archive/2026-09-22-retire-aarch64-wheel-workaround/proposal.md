# Proposal: Retire Local aarch64 Euphonic Wheel Workaround

## Why

When this project was initialized, Euphonic 2.x had not yet published aarch64 Linux wheels to PyPI. To support developers on ARM Linux (aarch64), a temporary workaround was put in place: a local `wheels/` directory was gitignored, `pyproject.toml` declared `[tool.uv] find-links = ["wheels"]`, container Dockerfiles copied `wheels/`, and documentation instructed aarch64 users to obtain a pre-release wheel manually.

Euphonic now publishes official 2.x wheels for both x86_64 and aarch64 Linux on PyPI. The temporary local wheel workaround is obsolete and can be removed, streamlining project configuration, Dockerfile build contexts, and onboarding documentation while treating all supported CPU architectures uniformly.

## What Changes

- Remove `[tool.uv] find-links = ["wheels"]` and associated workaround comments from `pyproject.toml`.
- Remove the `wheels/` directory and `wheels/.gitkeep`.
- Remove `wheels/*.whl` from `.gitignore`.
- Remove `COPY wheels /tmp/deps/wheels` from `tests/container/Dockerfile`.
- Clean up `get_find_links_from_pyproject` and `--find-links` plumbing in `tests/conftest.py`.
- Remove the `### aarch64 Euphonic wheel (local workaround)` section from `README.md`.
- Update `openspec/config.yaml` to remove references to local wheel staging.

## Capabilities

### New Capabilities

*(None)*

### Modified Capabilities

- `plugin-packaging`: Update `Requirement: Euphonic installs from PyPI wherever wheels are published` to state that Euphonic resolves directly from PyPI across all supported platforms (including x86_64 and aarch64 Linux) without requiring a local wheel directory or platform-specific workarounds.

## Non-goals

- Changing the Euphonic version constraint (`~=2.0`).
- Dropping support for aarch64 Linux (aarch64 Linux remains a fully supported platform).

## Impact

- `pyproject.toml`: Strips `[tool.uv]` find-links table and legacy comments.
- `README.md`: Removes manual wheel staging instructions.
- `tests/container/Dockerfile`: Eliminates `COPY wheels` step from the build layer.
- `tests/conftest.py`: Simplifies `AiiDAFreeEnvBuilder` by removing `find_links` handling.
- `openspec/config.yaml`: Updates project context to reflect direct PyPI installation.
