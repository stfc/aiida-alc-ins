## Context

aiida-pythonjob-ins currently requires Python >=3.11 and depends on abinslib==0.1.* from PyPI. The abinslib `py310-0.1` branch now provides Python 3.10 support, but is not yet released to PyPI.

This design covers how to add Python 3.10 support with Python-version-conditional sources for the abinslib dependency.

## Goals / Non-Goals

**Goals:**
- Enable Python 3.10 users to install and use aiida-pythonjob-ins
- Use abinslib's `py310-0.1` branch for Python 3.10 users
- Keep resins as an explicit dependency (used directly; abinslib may make it optional)

**Non-goals:**
- Changing the abinslib version constraint for Python 3.11+ (stays at 0.1.*)
- Modifying abinslib or resins packages (separate efforts)
- Supporting Python versions older than 3.10

## Decisions

### Decision 1: Use Python-version-conditional sources for abinslib

Use PEP 508 environment markers to specify different abinslib sources based on Python version:

```toml
dependencies = [
    "abinslib @ git+https://github.com/ISISNeutronMuon/abINS_lib@py310-0.1 ; python_version == '3.10'",
    "abinslib==0.1.* ; python_version >= '3.11'",
]
```

**Alternatives considered:**
- Separate optional dependencies per Python version: Rejected because it fragments the package and doesn't make abinslib a core dependency.
- Wait for abinslib PyPI release: Rejected because downstream users need Python 3.10 support now.

**Rationale:** The git dependency provides Python 3.10 support while the PyPI release serves Python 3.11+ users. The resolver selects the appropriate source based on the Python version.

### Decision 2: Import Self from typing_extensions

Change all `from typing import Self` to `from typing_extensions import Self`.

**Rationale:** `typing.Self` is a Python 3.11+ feature. To support Python 3.10, we import `Self` from `typing_extensions` instead. This is the same approach used in abinslib.

### Decision 3: Keep resins as explicit dependency

Keep `resins~=0.1.0` as an explicit dependency in addition to abinslib's resins dependency.

**Rationale:** aiida-pythonjob-ins uses resins directly, and abinslib may yet make resins an optional dependency. Keeping it explicit ensures it's always available.

**Note:** The resolver will use abinslib's resins dependency (git branch for Python 3.10, PyPI for 3.11+) since the constraints are compatible.

### Decision 4: Add ruff target-version = "py310"

Configure ruff to target Python 3.10 syntax.

**Rationale:** This ensures linting rules are appropriate for the minimum supported Python version.

### Decision 5: Update CI test matrix

Include Python 3.10, 3.11, and 3.14 in the CI test matrix.

**Rationale:** Test the minimum version (3.10), an intermediate version (3.11), and the latest version (3.14).

## Risks / Trade-offs

### Risk: Git dependency stability

**Risk:** The `py310-0.1` branch could change or be force-pushed.

**Mitigation:** The `py310-0.1` branch is maintained with cherry-picks only (no force-pushes expected). For critical reproducibility, users can pin to a specific commit in their own requirements.

### Risk: Dependency resolver complexity

**Risk:** Multiple abinslib declarations could confuse the resolver.

**Mitigation:** The Python-version markers are mutually exclusive, so the resolver will only consider one source at a time.

### Risk: resins version conflicts

**Risk:** Different resins versions from abinslib and aiida-pythonjob-ins could conflict.

**Mitigation:** The resins version constraints are compatible: abinslib specifies `resins == 0.1.0` for Python 3.11+ and the git branch for Python 3.10. aiida-pythonjob-ins specifies `resins~=0.1.0`, which is compatible with both.

## Migration Plan

This is a new capability, not a breaking change. Existing users on Python 3.11+ are unaffected. Python 3.10 users can now install and use the package.
