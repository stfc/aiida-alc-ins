## 1. Implement the check

- [x] 1.1 Add a test module that launches `sys.executable` via `subprocess` with
  `AIIDA_PATH` removed from the child environment, imports the operations module
  there, and reports what it observed as JSON on stdout; verify the child exits
  zero and reports no AiiDA import on the current tree.
- [x] 1.2 In the child, before any other import, insert a `sys.meta_path` finder
  whose `find_spec` records AiiDA module names and returns `None`, capturing
  `traceback.extract_stack()` on the first hit only and dropping frames whose
  filename lies inside AiiDA; verify the recorder does not block imports (a
  deliberate `import aiida` in the child still succeeds) and that the captured
  chain is a handful of frames rather than the several hundred that recording
  every hit produces.
- [x] 1.3 Have the parent decide pass or fail and render the message: on a
  contract violation, fail naming the AiiDA module and printing the blame chain
  as `file:line  source`; on a non-zero child exit, fail and include the child's
  stderr verbatim; verify both messages by forcing each condition.
- [x] 1.4 Match AiiDA modules as `aiida` or names beginning with `aiida.`, not by
  bare prefix; verify by confirming a bare-prefix match would report this
  package's own module while the implemented match reports nothing.
- [x] 1.5 Extend the same child to call one operation on a bundled fixture file
  after the import check, and re-check for AiiDA modules afterwards; verify the
  operation returns its Euphonic result and the second check still reports none.

## 2. Confirm the check has teeth

- [x] 2.1 Temporarily add an `import aiida` to `operations.py`, confirm the new
  test fails, names AiiDA as loaded and blames that line of `operations.py`,
  then revert; verify `git diff` is empty afterwards.
- [x] 2.2 Temporarily add a module that `operations.py` imports only
  indirectly - at least two hops away - and give *that* module a
  `from aiida.orm import Dict`; confirm the test fails and the blame chain names
  every hop from `operations.py` to the offending line, then revert; verify
  `git diff` is empty afterwards. This is the regression the check exists for,
  and the one a static or in-process check cannot see.
- [x] 2.3 Temporarily add a lazy `import aiida` inside the body of the operation
  exercised in 1.5, confirm the post-execution check fails, then revert; verify
  `git diff` is empty afterwards.

## 3. Verification

- [x] 3.1 Run `uv run pytest -m "not containerized"` and confirm the new test
  passes alongside the existing suite with no new warnings.
- [x] 3.2 Run `uv run ruff check` and `uv run ruff format --check` and confirm
  both pass.
- [x] 3.3 Confirm the test needs no container engine, no network and no new
  dependency: it passes with the network disabled and with
  `-p no:cacheprovider`.
