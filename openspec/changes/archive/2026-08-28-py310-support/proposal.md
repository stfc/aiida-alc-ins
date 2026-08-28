## Why

aiida-pythonjob-ins currently requires Python >=3.11, but downstream users need to run it in Python 3.10 environments. The abinslib dependency now has a `py310-0.1` branch that provides Python 3.10 support via git, while the PyPI release remains at 0.1.* for Python 3.11+.

This change documents the already-implemented Python 3.10 support.

## What Changes

- Lower minimum Python version from `>=3.11` to `>=3.10`
- Add `typing-extensions>=4.0.0` dependency for `Self` backport
- Update abinslib dependency with Python-version-conditional sources:
  - Python 3.10: install from git branch `py310-0.1` at `github.com/ISISNeutronMuon/abINS_lib`
  - Python 3.11+: install from PyPI (`abinslib==0.1.*`)
- Update source files to import `Self` from `typing_extensions` instead of `typing`
- Update CI test matrix to include Python 3.10

## Capabilities

### New Capabilities

- `runtime-compatibility`: Python 3.10 runtime support with conditional dependency sources for abinslib

### Modified Capabilities

None.

## Impact

**Affected files:**
- `pyproject.toml` - Python version, dependencies
- `src/aiida_pythonjob_ins/data/base.py` - typing import
- `src/aiida_pythonjob_ins/data/crystal.py` - typing import
- `src/aiida_pythonjob_ins/data/force_constants.py` - typing import
- `.github/workflows/ci.yml` - test matrix

**Dependencies:**
- `abinslib` now uses Python-version-conditional sources (git for 3.10, PyPI for 3.11+)
- `typing-extensions>=4.0.0` added as a dependency

**Non-goals:**
- Changing abinslib or resins packages (separate efforts)
- Adding Python 3.10 support for any other dependencies
- Modifying the core functionality or API of aiida-pythonjob-ins
