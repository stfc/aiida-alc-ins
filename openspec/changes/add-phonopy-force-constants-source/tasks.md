# Tasks

Notes for the implementer:

- Run all commands from `/workspace/aiida_pythonjob_ins`.
- design.md holds the code shapes, the exact exception tuple, the validator
  message, file checksums and the verified framework behaviour. Read it first,
  and follow it rather than re-deriving.
- Equivalence in tests means comparing with a direct
  `euphonic.ForceConstants.from_phonopy(...)` call on the same files, not with
  hard-coded numbers. Do not add tests that only check that sample files exist
  or are well formed.

## 1. Sample data and reader spike

- [x] 1.1 Create `tests/data/phonopy/NaCl_hdf5/` and download the four files
  listed in design.md Decision 6 from the pinned upstream commit, using the URL
  pattern given there. For example:
  `curl -fO <url>` for each of `phonopy_nofc_noborn.yaml`,
  `force_constants.hdf5`, `BORN_nacl` and `phonopy_nacl.yaml`. Append a
  `## phonopy/NaCl_hdf5/` section to `tests/data/README.md`, in the same style
  as the ethanol entry: a short description, Origin (upstream repo and path),
  Upstream commit, and one SHA-256 line per file. Verify that
  `sha256sum tests/data/phonopy/NaCl_hdf5/*` prints exactly the four checksums
  in design.md Decision 6.
- [x] 1.2 Spike, done during planning with throwaway scripts that have been
  deleted. It confirmed:
  - separate-directory and absolute-path reading;
  - `as_path()` file-name preservation and provenance links;
  - the exception classes;
  - plumpy's handling of the namespace.

  The results are recorded as **(verified)** items in design.md Decisions 1–6.
  No further spike is needed.

## 2. Library-level HDF5 coverage

- [x] 2.1 In `tests/conftest.py`, add a `phonopy_hdf5_dir` fixture returning
  `DATA_DIR / "phonopy" / "NaCl_hdf5"`, with a one-line docstring naming its
  source. Model it on the existing `phonopy_dir` fixture.
- [x] 2.2 In `tests/test_operations.py`, add
  `test_read_force_constants_from_phonopy_hdf5(phonopy_hdf5_dir, monkeypatch)`:
  - `monkeypatch.chdir(phonopy_hdf5_dir)`;
  - call `read_force_constants_from_phonopy(summary_name="phonopy_nofc_noborn.yaml",
    fc_name="force_constants.hdf5", born_name="BORN_nacl")`;
  - assert that its `force_constants`, `crystal.cell_vectors`, `born` and
    `dielectric` magnitudes equal those from
    `ForceConstants.from_phonopy(path=phonopy_hdf5_dir, ...)` with the same
    names, using `np.testing.assert_allclose`.

  Verify with
  `uv run pytest tests/test_operations.py -k phonopy_hdf5`.
- [x] 2.3 Docstring-only edits; do not change any code:
  - In `src/aiida_pythonjob_ins/pythonjobs.py` (`prepare_read_phonopy_inputs`),
    add the `.. note::` block from design.md Decision 8 after the summary line,
    in the same position as the note in `prepare_read_force_constants_inputs`.
    Also add one sentence: the force-constants file may be HDF5 (file name
    ending `.hdf5`, `.hd5` or `.h5`) or Phonopy text format.
  - In `src/aiida_pythonjob_ins/operations.py`
    (`read_force_constants_from_phonopy`), add the same HDF5-or-text sentence,
    and one sentence saying it exists to be run by
    `prepare_read_phonopy_inputs` and is likely to be removed with it before
    version 1.0.

  Leave the existing tests of both functions unchanged. Verify with
  `uv run ruff check`, `uv run ruff format --check` and
  `uv run pytest tests/test_operations.py tests/test_pythonjobs.py`.

## 3. Phonopy source on `ForceConstantsWorkChain`

- [x] 3.1 In `src/aiida_pythonjob_ins/workflows/force_constants.py`:
  - add `import contextlib` and `import yaml`;
  - add the module constant `PHONOPY_READ_ERRORS`;
  - add the `read_phonopy_force_constants` calcfunction, exactly as in design.md
    Decisions 3 and 4, placed after `read_castep_force_constants`. Its docstring
    covers:
    - in-process read, no job;
    - each file read from its own temporary copy;
    - `force_constants` omitted when the summary embeds force constants;
    - HDF5 detected by file-name suffix;
    - foreseeable failures returning `ExitCode(300, ...)`, other exceptions
      propagating.

  Verify that `uv run python -c "from aiida_pythonjob_ins.workflows.force_constants import read_phonopy_force_constants"`
  succeeds. If the `| None` annotations fail, apply the fallback in design.md
  Risks.
- [x] 3.2 In `tests/test_workflows.py`:
  - add a module-level helper `_assert_equivalent_force_constants(actual,
    expected)`, taking two `euphonic.ForceConstants`. It uses
    `np.testing.assert_allclose` on `force_constants.magnitude`,
    `crystal.cell_vectors.magnitude` and `crystal.atom_r`, asserts that
    `crystal.atom_type` is equal, and asserts that `born` and `dielectric` are
    both `None` or both all-close;
  - add `_phonopy_nodes(directory, **names)`, returning
    `{key: SinglefileData(directory / name)}` for each given key and file name;
  - import `read_phonopy_force_constants`.

  Then add these calcfunction tests next to the CASTEP calcfunction tests. Each
  launches with `run_get_node(read_phonopy_force_constants, **nodes)`, and each
  equivalence test compares `result.get_force_constants()` with a direct
  `ForceConstants.from_phonopy(path=<dir>, summary_name=..., fc_name=...,
  born_name=...)` call:
  - `test_read_phonopy_force_constants_hdf5`: HDF5 and Born from
    `phonopy_hdf5_dir`. Finishes ok, the node is a `CalcFunctionNode`, the result
    is `ForceConstantsData` and equivalent, and `node.inputs` contains
    `summary`, `force_constants` and `born`.
  - `test_read_phonopy_force_constants_hdf5_without_born`: HDF5 only.
    Equivalent, and `born` is `None`.
  - `test_read_phonopy_force_constants_text_format`: `phonopy_dir` files
    `phonopy.yaml`, `FORCE_CONSTANTS` and `BORN`. Equivalent.
  - `test_read_phonopy_force_constants_embedded_summary`: `phonopy_nacl.yaml`
    only. Equivalent to `ForceConstants.from_phonopy(path=phonopy_hdf5_dir,
    summary_name="phonopy_nacl.yaml")`.
  - `test_read_phonopy_force_constants_missing_force_constants`:
    `phonopy_nofc_noborn.yaml` only. `node.exit_status == 300`, and
    `"Could not read Phonopy force constants"` is in `node.exit_message`.
  - `test_read_phonopy_force_constants_corrupt_hdf5(tmp_path)`: the summary plus
    a `tmp_path / "force_constants.hdf5"` containing junk bytes. Exit status 300.
  - `test_read_phonopy_force_constants_unrelated_error_propagates(tmp_path)`:
    use `patch.object(ForceConstantsData, "from_phonopy",
    side_effect=RuntimeError("Something completely different"))` with
    `pytest.raises(RuntimeError, ...)`, following the existing
    `test_read_castep_force_constants_unrelated_runtime_error_propagates`.
    Assert that the error propagates, and not exit 300.

  Verify with `uv run pytest tests/test_workflows.py -k read_phonopy`.
- [x] 3.3 In `ForceConstantsWorkChain`:
  - add the `phonopy` namespace and three ports, with the help texts in
    design.md Decision 1;
  - replace `_validate_source`;
  - add `has_phonopy` and `read_phonopy`;
  - change the outline as in design.md Decision 5;
  - update the class docstring: three sources, the Phonopy calcfunction, exit
    410 for a failed read from any file source;
  - update the module docstring's first paragraph, which currently says "a
    CASTEP `castep_file` ... or a prepared `node`";
  - update the `node` port help text to "A prepared `ForceConstantsData`,
    built by any means; passed through unchanged."

  Verify with `uv run ruff check`.
- [x] 3.4 Add workchain tests in `tests/test_workflows.py`. Add
  `ForceConstantsWorkChain` to the existing `from aiida_pythonjob_ins.workflows
  import (...)` block; it is already re-exported there. These tests need no
  `python_code` fixture:
  - `test_force_constants_workchain_from_phonopy_hdf5`: the HDF5, Born and
    summary set. Finishes ok. The `force_constants` output is equivalent to the
    direct Euphonic read, and exactly one `CalcFunctionNode` with
    `process_label == "read_phonopy_force_constants"` is in `node.called`.
  - `test_force_constants_workchain_rejects_multiple_sources` (parametrized
    over the pairs `castep_file`+`phonopy`, `phonopy`+`node`,
    `castep_file`+`node`, and all three): `pytest.raises(ValueError,
    match="exactly one of `castep_file`, `phonopy` or `node`")`. Use
    `quartz_castep_bin` for the CASTEP file and a `ForceConstantsData` from the
    HDF5 set for `node`.
  - `test_force_constants_workchain_rejects_no_source`: launched with no inputs,
    raises the same error.
  - `test_force_constants_workchain_phonopy_requires_summary`: `phonopy={"born":
    ...}` only. `pytest.raises(ValueError, match="summary")`.
  - `test_force_constants_workchain_unreadable_phonopy_exits_410`: the summary
    `phonopy_nofc_noborn.yaml` only. `node.exit_status == 410`, and
    `"force_constants" not in node.outputs`.
  - `test_force_constants_workchain_node_passthrough_ignores_empty_phonopy`:
    `node` only. Finishes ok, the output is the same node (compare `.uuid`), and
    `node.called` is empty. This guards the empty-namespace truthiness check in
    design.md Decision 5.

  Leave the existing `test_workchain_requires_exactly_one_source` unchanged; it
  must still pass. Verify with
  `uv run pytest tests/test_workflows.py -k "force_constants_workchain or exactly_one"`.

## 4. Consumer workflows and documentation

- [x] 4.1 Add consumer tests in `tests/test_workflows.py`:
  - `test_dispersion_from_phonopy_files(python_code, phonopy_hdf5_dir)`: launch
    `DispersionWorkChain` with `force_constants={"phonopy": <HDF5 + Born +
    summary nodes>}` and `q_spacing=Float(0.3)`. Finishes ok, and
    `band_structure` is `BandsData`. Exactly one `ForceConstantsWorkChain`
    appears in `called_descendants`, and that child's `outputs.force_constants`
    is equivalent to the direct Euphonic read.
  - `test_dos_from_phonopy_files(python_code, phonopy_hdf5_dir)`: the same files
    with `DosWorkChain`, `q_spacing=Float(0.5)` and
    `energy_spacing=Float(2.0)`. Finishes ok, and `dos` is `XyData`.
  - `test_tosca_from_force_constants_exposes_phonopy_namespace()`: assert that
    `"phonopy" in ToscaFromForceConstantsWorkChain.spec().inputs["force_constants"]`,
    and that the namespace holds the ports `summary`, `force_constants` and
    `born`.

  Verify with `uv run pytest tests/test_workflows.py -k "phonopy"`.
- [x] 4.2 Rework `docs/source/tutorials/plot_phonopy_bands_and_dos.py` exactly
  as described in design.md Decision 7, keeping the `WorkflowFactory` loading
  and the comment that direct imports also work. Verify with
  `uv run ruff check docs/source/tutorials` and with the docs build in 4.4.
- [x] 4.3 Update the prose that lists the sources:
  - **`README.md`, "What's implemented":** in the "Input formats" bullet, say
    that Phonopy is `phonopy.yaml` + `FORCE_CONSTANTS` or
    `force_constants.hdf5` [+ `BORN`]. In the "Workflows" bullet, list three
    sources (`castep_file`, a `phonopy` namespace of `summary`/`force_constants`/
    `born`, or `node`). In the `ForceConstantsWorkChain` sub-bullet, say that it
    reads CASTEP or Phonopy files in-process with a `calcfunction`.
  - **`README.md`, "Usage sketch":** add a short second launch below the CASTEP
    one, showing `force_constants={"phonopy": {"summary":
    orm.SinglefileData("phonopy.yaml"), "force_constants":
    orm.SinglefileData("force_constants.hdf5")}}`.
  - **`docs/source/workflows.rst`:** in the intro paragraph (around lines 5 and
    10), name the three sources and add `force_constants={"phonopy": {...}}` to
    the example list. Around line 57, change "(`castep_file` or `node`)" to
    "(`castep_file`, `phonopy` or `node`)".
  - **`CHANGELOG.md`:** under `## [Unreleased]` / `### Added`, add an entry:
    `ForceConstantsWorkChain`, and so every force-constants workflow, accepts a
    `phonopy` input namespace (`summary`, optional `force_constants` as HDF5 or
    text, optional `born`) read in-process; a failed read exits `410`.
    Under `### Changed`, add: `prepare_read_phonopy_inputs` is now documented
    as a demonstration of `PythonJob` file staging, since workflows read
    Phonopy files in-process; it is likely to be removed before version 1.0.

  Verify that ``grep -nE 'castep_file`+ or `+node' README.md docs/source/workflows.rst``
  (single quotes, so the shell does not interpret the backticks) returns
  nothing, and that README no longer says "*either* a CASTEP `castep_file`
  *or* a prepared".
- [x] 4.4 Build the docs with `uv run --group doc make -C docs html` (Graphviz
  and `ps` are available in the sandbox). Verify that the build finishes
  without warnings, the Phonopy example executes, and
  `docs/build/html/auto_examples/plot_phonopy_bands_and_dos.html` shows a band
  structure, a DOS figure and a provenance graph containing
  `read_phonopy_force_constants`.

## 5. Integration checks

- [x] 5.1 Run `uv run pytest`, `uv run ruff check` and
  `uv run ruff format --check`. Verify that all three pass.
- [x] 5.2 Run `openspec validate add-phonopy-force-constants-source` (from
  `/workspace` or `/workspace/aiida_pythonjob_ins`). Run `git status` in
  `aiida_pythonjob_ins` and confirm that it lists only:
  - the files named in this task list;
  - the new `tests/data/phonopy/NaCl_hdf5/`;
  - this change directory.

  There should be no scratch scripts and no test-of-test files. Verify that
  validation passes and no unexpected files appear.

## Workflow follow-up

- Archive the change after review. On archive, cut back any README text that
  duplicates the `phonon-workflows` spec to a pointer.
