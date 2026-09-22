# Design: Retire Local aarch64 Euphonic Wheel Workaround

## Context

During the initial baseline development of this plugin (`2026-08-12-document-poc-baseline`), Euphonic 2.x was not yet published on PyPI with aarch64 Linux wheels. To allow developers on ARM64 Linux systems (such as Apple Silicon running Linux VMs or ARM workstations) to run the plugin, a temporary local wheel workaround was implemented:
- `wheels/` directory containing `.gitkeep` (with `wheels/*.whl` ignored in `.gitignore`).
- `pyproject.toml` declaring `[tool.uv] find-links = ["wheels"]`.
- `tests/container/Dockerfile` copying `wheels/` into `/tmp/deps/` during image builds.
- `tests/conftest.py` reading `find-links` from `pyproject.toml` via `get_find_links_from_pyproject` and appending `--find-links` to child virtualenv installations.
- `README.md` detailing how aarch64 developers must manually obtain and unpack a pre-release wheel.

Decision 12 in `2026-08-12-document-poc-baseline/design.md` explicitly scheduled this workaround for deletion once Euphonic published official aarch64 wheels on PyPI. Official aarch64 wheels (`euphonic-2.0.0-cp312-cp312-manylinux_2_17_aarch64.whl`, etc.) are now available on PyPI.

## Goals / Non-Goals

**Goals:**
- Completely remove the `wheels/` directory, `[tool.uv] find-links` configuration, and associated `.gitignore` rules.
- Simplify `tests/container/Dockerfile` by removing `COPY wheels`.
- Clean up `tests/conftest.py` by removing `find_links` extraction and parameter passing.
- Streamline `README.md` and `openspec/config.yaml` to treat all supported CPU architectures uniformly.

**Non-Goals:**
- Modifying runtime dependencies or relaxing Euphonic version constraints.
- Modifying container image base or Python runtime versions.

## Decisions

### Decision 1: Remove `[tool.uv]` find-links table from `pyproject.toml`
- **Choice**: Delete the `[tool.uv]` table and its `find-links = ["wheels"]` setting.
- **Rationale**: If `find-links` remained while `wheels/` was deleted, `uv` would raise an error (`error: Failed to read --find-links directory: wheels`). Removing the table restores standard, purely index-based package resolution.

### Decision 2: Remove `wheels/` directory and `.gitignore` entries
- **Choice**: Delete `wheels/.gitkeep` and remove the `wheels/` directory, and remove `wheels/*.whl` and its introductory comment from `.gitignore`.
- **Rationale**: Eliminates dead scaffolding and prevents confusion for new contributors.

### Decision 3: Remove `COPY wheels` from `tests/container/Dockerfile`
- **Choice**: Remove `COPY wheels /tmp/deps/wheels` from Stage 1 of `tests/container/Dockerfile`.
- **Rationale**: The Dockerfile builds on both x86_64 and aarch64. With `find-links` removed from `pyproject.toml`, `uv sync --no-install-project` resolves all dependencies directly from PyPI.

### Decision 4: Clean up `AiiDAFreeEnvBuilder` in `tests/conftest.py`
- **Choice**: Remove `get_find_links_from_pyproject()` and the `find_links` parameter from `AiiDAFreeEnvBuilder`.
- **Rationale**: The helper was created solely to forward `[tool.uv] find-links` to `pip install` when building the child virtual environment. Removing it eliminates dead code and simplifies fixture initialization.

### Decision 5: Documentation & Context Alignment
- **Choice**: Remove the `### aarch64 Euphonic wheel (local workaround)` subsection from `README.md`. Update commentary in `pyproject.toml` and `openspec/config.yaml`.
- **Rationale**: Developer onboarding becomes frictionless on all platforms (`uv sync` and `uv run pytest` work out of the box with no special-case steps).

## Risks / Trade-offs

- **[Risk]** Developers with cached local dev wheels might see dependency version drift.  
  $\rightarrow$ **Mitigation**: Upstream PyPI provides the exact `euphonic==2.0.0` release. Running `uv sync` resolves the standard release wheel.
