## 1. Remove the declaration

- [ ] 1.1 Delete `"pytest-xdist>=3"` from `[dependency-groups].dev` in
  `pyproject.toml` and regenerate the lock; verify with `uv sync` followed by
  `uv run python -c "import xdist"` failing with `ModuleNotFoundError`.
- [ ] 1.2 Record the ad-hoc invocation
  (`uv run --with pytest-xdist pytest -n auto -m "not containerized"`) in the
  contributor-facing documentation, noting that containerized tests are excluded
  because their session-scoped container fixture is not yet xdist-safe; verify
  the note renders in the built docs.

## 2. Verification

- [ ] 2.1 Run `uv run pytest -m "not containerized"` and confirm the same
  results as before the change.
- [ ] 2.2 Run `uv run ruff check` and `uv run ruff format --check`.
- [ ] 2.3 Confirm the documented ad-hoc invocation actually works, so the
  capability really is preserved rather than merely claimed.
