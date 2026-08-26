## 1. Implement the check

- [ ] 1.1 Add a test module that launches `sys.executable` via `subprocess` with
  `AIIDA_PATH` removed from the child environment, imports the operations module
  there, and reports the loaded AiiDA modules; verify the child exits zero and
  reports none on the current tree.
- [ ] 1.2 Match AiiDA modules as `aiida` or names beginning with `aiida.`, not by
  bare prefix; verify by confirming a bare-prefix match would report this
  package's own module while the implemented match reports nothing.
- [ ] 1.3 Extend the same child to call one operation on a bundled fixture file
  after the import check, and re-check for AiiDA modules afterwards; verify the
  operation returns its Euphonic result and the second check still reports none.

## 2. Confirm the check has teeth

- [ ] 2.1 Temporarily add an `import aiida` to `operations.py`, confirm the new
  test fails and names AiiDA as loaded, then revert; verify `git diff` is empty
  afterwards.
- [ ] 2.2 Temporarily add a lazy `import aiida` inside the body of the operation
  exercised in 1.3, confirm the post-execution check fails, then revert; verify
  `git diff` is empty afterwards.

## 3. Verification

- [ ] 3.1 Run `uv run pytest -m "not containerized"` and confirm the new test
  passes alongside the existing suite with no new warnings.
- [ ] 3.2 Run `uv run ruff check` and `uv run ruff format --check` and confirm
  both pass.
- [ ] 3.3 Confirm the test needs no container engine, no network and no new
  dependency: it passes with the network disabled and with
  `-p no:cacheprovider`.
