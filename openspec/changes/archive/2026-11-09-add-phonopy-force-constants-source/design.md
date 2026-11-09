# Design: Phonopy files as a force-constants source for workflows

See proposal.md (Why) for motivation and `specs/` for the required behaviour.
This document records the decisions and gives enough implementation detail for
the work in tasks.md to proceed without further investigation. Every behaviour
marked **(verified)** was confirmed by a throwaway spike against
aiida-core 2.x, plumpy and Euphonic 2.0.0 as locked in `uv.lock`, using the
upstream Euphonic NaCl files listed in Decision 6.

## Context

Current state of the code this change touches:

- `src/aiida_pythonjob_ins/workflows/force_constants.py` defines:
  - the `read_castep_force_constants(castep_file)` calcfunction. It returns
    `ForceConstantsData` or `ExitCode(300, "Could not read CASTEP force
    constants: ...")`.
  - `ForceConstantsWorkChain`, with:
    - ports `castep_file` (`SinglefileData`, optional) and `node`
      (`ForceConstantsData`, optional);
    - the validator `_validate_source`, which returns
      `"Provide exactly one of `castep_file` or `node`."`;
    - the outline `if_(cls.has_castep_file)(cls.read_castep_file).else_(cls.use_node), cls.finalize`;
    - exit code `410 ERROR_READ_FAILED`.

  `read_castep_file` calls `read_castep_force_constants.run_get_node(...)`. If
  the node is not `is_finished_ok`, it calls `self.report(node.exit_message)`
  and returns `self.exit_codes.ERROR_READ_FAILED`. Otherwise it stores the
  result in `self.ctx.force_constants`.
- `src/aiida_pythonjob_ins/workflows/base.py`:
  - `FromForceConstantsWorkChain` calls
    `spec.expose_inputs(ForceConstantsWorkChain, namespace="force_constants")`.
  - `DispersionWorkChain`, `DosWorkChain` and `ToscaFromForceConstantsWorkChain`
    inherit it. A new port on `ForceConstantsWorkChain` therefore appears in all
    three as `force_constants.<port>` with **no code change in base.py or the
    consumers**.
- `ForceConstantsData.from_phonopy(**kwargs)` in
  `src/aiida_pythonjob_ins/data/force_constants.py` returns
  `cls(ForceConstants.from_phonopy(**kwargs))`.
- A PythonJob-based Phonopy reader already exists:
  `pythonjobs.prepare_read_phonopy_inputs` runs
  `operations.read_force_constants_from_phonopy` inside a `PythonJob`. Until
  now it was the only way to turn Phonopy files into a workflow input, and the
  Phonopy tutorial is built around it. Its CASTEP counterpart,
  `prepare_read_force_constants_inputs`, already carries a note that it only
  demonstrates PythonJob file staging and that no workflow uses it. It is still
  exercised by `tests/test_remote_ssh.py`.

Upstream behaviour this design relies on:

- `euphonic.ForceConstants.from_phonopy(path, summary_name, born_name, fc_name,
  fc_format)`, implemented in
  `euphonic.readers.phonopy.read_interpolation_data`. Docs:
  <https://euphonic.readthedocs.io/en/stable/force-constants.html#reading-from-phonopy>.
  - It reads the summary first. It opens `fc_name` only if the summary contains
    no force constants. It opens `born_name` only if a name is given and the
    summary lacks Born or dielectric data.
  - It builds each path as `Path(path) / name`.
  - It chooses HDF5 if the `fc_name` suffix is in `{'hdf5', 'hd5', 'h5'}` and
    text otherwise.
  - It writes progress lines to stdout with `print`.
- `SinglefileData.as_path()` is a context manager. It copies the stored content
  (streamed, not loaded into memory) into a fresh `TemporaryDirectory`, under
  the node's stored `filename`, and yields that path. Source: aiida-core
  `NodeRepository.as_path`;
  <https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/data_types.html#singlefile>.

## Goals / Non-Goals

**Goals:**

- Any force-constants workflow accepts Phonopy files as `SinglefileData` under
  `force_constants.phonopy`, with one provenance graph from the files to the
  results.
- The provenance shape (one calcfunction) and failure contract (300, mapped to
  410) match the CASTEP source.
- HDF5 input is tested at operation and workflow level.

**Non-Goals:**

- Changing the behaviour of `prepare_read_phonopy_inputs` or
  `read_force_constants_from_phonopy`, or removing them. Only their docstrings
  change (Decision 8).
- Validating file contents beyond what Euphonic's reader does.
- Exposing Euphonic's `fc_format` argument (Decision 2).

## Decisions

### 1. A `phonopy` input namespace with `summary`, `force_constants`, `born`

`ForceConstantsWorkChain.define` gains:

```python
spec.input_namespace(
    "phonopy",
    required=False,
    help="Phonopy output files; read in-process by `read_phonopy_force_constants`.",
)
spec.input(
    "phonopy.summary",
    valid_type=SinglefileData,
    help="Phonopy summary file (`phonopy.yaml`). Required when `phonopy` is used.",
)
spec.input(
    "phonopy.force_constants",
    valid_type=SinglefileData,
    required=False,
    help=(
        "Force-constants file: HDF5 if the file name ends in .hdf5/.hd5/.h5, "
        "otherwise Phonopy text format (FORCE_CONSTANTS). Omit if the summary "
        "already contains force constants."
    ),
)
spec.input(
    "phonopy.born",
    valid_type=SinglefileData,
    required=False,
    help="Born-charges file (BORN). Ignored if the summary already holds Born data.",
)
```

The names match the parameters of `prepare_read_phonopy_inputs`.

**(verified)** Plumpy treats this namespace as follows:

- An omitted `phonopy` namespace passes validation, although `summary` inside it
  is required.
- A namespace given with `born` but no `summary` is rejected at launch with
  `ValueError: Error occurred validating port 'inputs.phonopy.summary': required
  value was not provided for 'summary'`. No custom code is needed for the "no
  summary" scenario.

Rationale and rejected alternatives:

- **Why a namespace:** the three files form one source, and plumpy enforces
  "summary required" inside it.
- **Rejected: flat ports** (`phonopy_summary`, ...). They clutter every
  consumer's `force_constants` namespace and need a hand-written "summary
  required if any other Phonopy port is set" rule.
- **Rejected: one `FolderData`.** It hides which file is which, and file-upload
  widgets (for example in AiiDAlab) produce `SinglefileData`.
- **Why `force_constants` is optional:** a summary with embedded force constants
  is a complete source on its own.
- **Why `born` is included:** the underlying call supports it, and it matters
  for polar materials.

**Downstream (AiiDAlab) impact:** the change only adds inputs. Existing callers
are unaffected. A builder-driven form shows one more nested group. Exclusivity
stays a spec-level validator, as today.

### 2. Accept both HDF5 and text; do not expose `fc_format`

**(verified)** `SinglefileData` keeps the original file name, so
`force_constants.hdf5` keeps its suffix through `as_path()`, and Euphonic reads
it as HDF5.

- **Rejected: restricting to HDF5.** It would add a check and remove no code,
  because both formats go through the same call.
- **Rejected: an `fc_format` input.** It is needed only when an HDF5 file is
  stored without an HDF5 suffix. **(verified)** Such a file is read as text and
  raises `UnicodeDecodeError`, a subclass of `ValueError`. That is caught by
  Decision 4 and ends in a clean 410 whose message includes the Euphonic error.
  The port help text states the suffix convention.

### 3. Read in-process with a calcfunction next to the CASTEP reader

Add this calcfunction to `workflows/force_constants.py`, below
`read_castep_force_constants`:

```python
@calcfunction
def read_phonopy_force_constants(
    summary: SinglefileData,
    force_constants: SinglefileData | None = None,
    born: SinglefileData | None = None,
) -> ForceConstantsData | ExitCode:
    """<docstring: purpose, path handling, failure contract -- see below>"""
    try:
        with contextlib.ExitStack() as stack:
            summary_path = stack.enter_context(summary.as_path())
            kwargs = {"path": summary_path.parent, "summary_name": summary_path.name}
            if force_constants is not None:
                kwargs["fc_name"] = str(stack.enter_context(force_constants.as_path()))
            if born is not None:
                kwargs["born_name"] = str(stack.enter_context(born.as_path()))
            return ForceConstantsData.from_phonopy(**kwargs)
    except PHONOPY_READ_ERRORS as exc:
        return ExitCode(300, f"Could not read Phonopy force constants: {exc}")
```

Imports needed in that module: `contextlib`, `yaml` (PyYAML is already installed
through aiida-core and `euphonic[phonopy-reader]`), and `if_` is already
imported.

**Path handling (verified):**

- Each file stays in its own temporary directory.
- `path` is the summary's directory.
- `fc_name` and `born_name` are absolute paths. `Path(path) / absolute` yields
  the absolute path (<https://docs.python.org/3/library/pathlib.html#pathlib.PurePath>).
- The result is identical, with force-constants arrays exactly equal, to reading
  all files from one shared directory.
- Every supplied file appears as an incoming link of the `CalcFunctionNode`,
  with link labels `summary`, `force_constants` and `born`.
- If `force_constants` is omitted and the summary has none, Euphonic looks for
  `<summary tempdir>/FORCE_CONSTANTS`, which cannot exist. The read therefore
  fails with `FileNotFoundError`, and it can never pick up a stray file from the
  daemon's working directory.

Rationale and rejected alternatives:

- **Why in-process:** the read is cheap, comparable to the CASTEP read, which
  the project already moved from PythonJob to a calcfunction for that reason. A
  calcfunction is also cacheable.
- **Rejected: a child PythonJob.** `ForceConstantsWorkChain` is specified to
  take no `Code`.
- **Rejected: copying all inputs into one shared directory.** It needs the same
  number of copies, adds code, and risks name collisions.
- **Rejected: symlinking repository objects.** There is no public aiida-core API
  for a stable on-disk path, because the object store may pack objects.

### 4. Classified failures return `ExitCode(300)`; the workchain maps it to 410

Define at module level in `workflows/force_constants.py`:

```python
#: Exceptions Euphonic's Phonopy reader raises for unreadable or invalid input
#: (malformed summary, HDF5 or text file). Anything else is a bug and propagates.
PHONOPY_READ_ERRORS = (OSError, ValueError, KeyError, TypeError, yaml.YAMLError)
```

**(verified)** Each class has an observed cause:

| Input defect | Exception raised by Euphonic |
|---|---|
| Summary has no force constants and no `force_constants` file given | `FileNotFoundError` (`OSError`) |
| Named Born file missing | `FileNotFoundError` (`OSError`) |
| HDF5 file that is junk or truncated | `OSError` (from h5py) |
| HDF5 file lacking the `force_constants` dataset | `KeyError` |
| HDF5 force constants of the wrong shape | `ValueError` ("Incompatible force constants") |
| HDF5 content stored without HDF5 suffix | `UnicodeDecodeError` (`ValueError`) |
| Junk text `FORCE_CONSTANTS` | `ValueError` |
| Junk `BORN` | `ValueError` |
| Summary not YAML (syntax error) | `yaml.parser.ParserError` (`yaml.YAMLError`) |
| Summary is binary junk | `UnicodeDecodeError` (`ValueError`) |
| Summary is valid YAML but not a Phonopy summary | `KeyError` |
| Summary is empty | `TypeError` (`'NoneType' object is not subscriptable`) |

`TypeError` and `KeyError` are broad. They are acceptable here because the `try`
body only opens files and makes one public Euphonic call. A wrong keyword in our
own call would also raise `TypeError` and be reported as exit 300, but the
positive tests in tasks.md (every valid input set must finish ok) catch that
immediately. This is a deliberate difference from the CASTEP reader, which can
match `RuntimeError` by message. The Phonopy reader's messages are not stable
enough to match. Any exception outside the tuple propagates, so the process is
Excepted. That matches the existing policy of returning exit codes for expected
failures:
<https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/processes/usage.html#exit-codes>.

- **Rejected: a separate Phonopy exit code.** The spec defines one read-failure
  code for any source.

### 5. Validator and outline

**(verified)** The `phonopy` key is **always present** in the validator's
`inputs` and in `self.inputs`, as an empty mapping when the caller omitted it.
That holds both when launched directly and through `expose_inputs` and
`exposed_inputs`. Presence must therefore be tested by **truthiness**, never by
`"phonopy" in inputs`.

```python
@staticmethod
def _validate_source(inputs, _port) -> str | None:
    """Require exactly one of ``castep_file`` / ``phonopy`` / ``node``."""
    given = [
        "castep_file" in inputs,
        bool(inputs.get("phonopy")),
        "node" in inputs,
    ]
    if sum(given) != 1:
        return "Provide exactly one of `castep_file`, `phonopy` or `node`."
    return None

def has_castep_file(self) -> bool: ...  # unchanged

def has_phonopy(self) -> bool:
    """Return whether a Phonopy file set was supplied as the source."""
    return bool(self.inputs.get("phonopy"))

def read_phonopy(self) -> ExitCode | None:
    """Read the supplied Phonopy files in-process and store the result."""
    result, node = read_phonopy_force_constants.run_get_node(**self.inputs.phonopy)
    if not node.is_finished_ok:
        self.report(node.exit_message)
        return self.exit_codes.ERROR_READ_FAILED
    self.ctx.force_constants = result
    return None
```

The outline becomes:

```python
spec.outline(
    if_(cls.has_castep_file)(cls.read_castep_file)
    .elif_(cls.has_phonopy)(cls.read_phonopy)
    .else_(cls.use_node),
    cls.finalize,
)
```

The validator message keeps the substring `exactly one`, which the existing test
`test_workchain_requires_exactly_one_source` matches with
`pytest.raises(ValueError, match="exactly one")`. `castep_file` and `node` are
only present when supplied, so `in` is correct for them.

### 6. Sample data from Euphonic's test suite

Add these files to a new directory, `tests/data/phonopy/NaCl_hdf5/`, keeping the
upstream names. They come from `pace-neutrons/Euphonic` at commit
`1d86683518f248f621539c2ddcbf7964b061b439`, path
`tests_and_analysis/test/data/phonopy_files/NaCl/`:

| File | Size | SHA-256 | Role |
|---|---|---|---|
| `phonopy_nofc_noborn.yaml` | 12.6 KB | `c71e9685963a3a5988b93d0b68f7f61cc089a54d51ba0f99a7fe7d5aa6bbe001` | Summary with neither force constants nor Born data |
| `force_constants.hdf5` | 11.8 KB | `1d3b038fc40dd4107289c1495307a6b72af7036a2710c6f6cf548de0ae86966e` | HDF5 force constants for that summary |
| `BORN_nacl` | 0.4 KB | `3961e05e92a9776f0e0bd578f35880525329335271d93cce9688447f65e8b68e` | Born charges and dielectric tensor |
| `phonopy_nacl.yaml` | 141.5 KB | `8a0aa1d1e5c6f0631bbe6ef405565ea1cfb4c6ce3fb370960c55075309a3a4a2` | Summary with embedded force constants and Born data |

Download URL pattern:
`https://raw.githubusercontent.com/pace-neutrons/Euphonic/1d86683518f248f621539c2ddcbf7964b061b439/tests_and_analysis/test/data/phonopy_files/NaCl/<file>`.

**(verified)** facts about this set:

- The HDF5 and Born set yields force constants of shape `(8, 24, 24)` with Born
  data present.
- Without `BORN_nacl`, `born` is `None`.
- `phonopy_nacl.yaml` alone yields Born data of shape `(8, 3, 3)`.

Coverage:

| Input combination | Scenario covered |
|---|---|
| HDF5 + Born | HDF5 read and separate Born file |
| HDF5 alone | Read without Born data |
| `phonopy_nacl.yaml` alone | Embedded summary |
| `phonopy_nofc_noborn.yaml` alone | Missing force constants, exit 300 / 410 |
| Existing `NaCl_default` (`phonopy.yaml`, `FORCE_CONSTANTS`, `BORN`) | Text format |

Record the provenance in `tests/data/README.md` with one `##` section for the
directory, following the existing `ethanol_qpoint_phonon_modes.json` entry:
Origin, Upstream commit, and a SHA-256 line per file.

### 7. The gallery example uses the workflow route

Rework `docs/source/tutorials/plot_phonopy_bands_and_dos.py` as follows:

- **Band structure:** run `DispersionWorkChain` with
  `force_constants={"phonopy": {"summary": ..., "force_constants": ...,
  "born": ...}}`. The values are `orm.SinglefileData(example_data("phonopy",
  "NaCl_hdf5", <file>))` for `phonopy_nofc_noborn.yaml`, `force_constants.hdf5`
  and `BORN_nacl`.
- **DOS:** `DispersionWorkChain` has no force-constants output, so take the
  resolved node from its child:
  `fc_child = next(c for c in bands_node.called if c.process_label == "ForceConstantsWorkChain")`,
  then `force_constants = fc_child.outputs.force_constants`. Run `DosWorkChain`
  with `force_constants={"node": force_constants}`. This shows both patterns and
  does not read the files twice.
- Remove the `prepare_read_phonopy_inputs` and `PythonJob` usage, and their
  imports. Do not add a closing paragraph about the builder: the gallery
  should not teach an API that is likely to be removed (Decision 8).
- Update the module docstring, which is the gallery page title and intro, and
  the provenance caption. The graph now runs from the files through
  `read_phonopy_force_constants` inside `ForceConstantsWorkChain`.
- Keep `show_provenance(bands_node, ...)` and the existing plotting code.

### 8. The Phonopy PythonJob builder is kept, labelled as a demonstration

Once workflows read Phonopy files in-process, `prepare_read_phonopy_inputs` has
no role in any workflow. A PythonJob read is also slower than the in-process
read for every case this package supports:

- it adds job overhead;
- it uploads the files to the job's working directory;
- it serializes the result back.

The one case where reading on the remote side could help is files that already
sit on the remote computer. The builder doesn't support that as written,
because it stages local paths or `SinglefileData`.

For now it is kept, with behaviour unchanged, and labelled the way the CASTEP
builder already is. Add this note to its docstring, after the summary line:

```rst
.. note::
   Demonstrates ``PythonJob`` file staging; no workflow uses it. Workflows
   read Phonopy files in-process through ``force_constants.phonopy``. Likely
   to be removed before version 1.0.
```

The docstring of `operations.read_force_constants_from_phonopy` gains one
sentence: it exists to be run by `prepare_read_phonopy_inputs`, and the same
likely removal applies. Neither docstring restates the HDF5-or-text rule
(Decision 9).

- **Rejected for now: removing the builder in this change.** Removal would mean
  changing the `pythonjob-execution` requirement that every read operation has
  a job builder, deleting two tests, and adding a breaking CHANGELOG entry. It
  is deferred to a separate change before version 1.0, which can also decide
  the CASTEP builder's future together with its role in `test_remote_ssh.py`.
- **Rejected: a `DeprecationWarning`.** The removal is likely, not decided. The
  docstring note and a CHANGELOG line state the intent without a
  runtime warning.

The `pythonjob-execution` and `phonon-operations` specs are unchanged by this
decision, and the existing tests of the builder stay as they are.

### 9. Docstrings: one home per fact, links elsewhere

The first implementation repeated several facts across the module, class,
calcfunction, step, operation and builder docstrings (the HDF5 suffix list in
three places, the in-process rationale in four). Each fact gets one home; the
other docstrings say less or link to it.

| Fact | Home | Elsewhere |
|---|---|---|
| Accepted `force_constants` formats and the suffix rule | `phonopy.force_constants` port help | Not restated; the calcfunction says only that the format is inferred from the stored file name |
| Why file reads are in-process, and provenance of the read | `ForceConstantsWorkChain` class docstring, one or two sentences | Calcfunctions and builder note do not repeat it |
| Exit codes 300 and 410 | Calcfunction return contract (300); class `Exit Codes:` (410) | Step methods get a one-line summary |
| Deprecation of the PythonJob builders | `.. note::` on `prepare_read_phonopy_inputs` | One clause on the operation |
| What the workchain does | Class docstring | Module docstring is a short pointer to the class and to `workflows.base` |

Further rules:

- Docstrings and code comments do not cite design decisions of an OpenSpec
  change, because the change is archived after merge. State the fact instead.
- A comment explaining a non-obvious `except` clause sits next to the clause,
  not in the calcfunction docstring (this applies to the CASTEP `RuntimeError`
  matching as well).
- `operations.py` stays free of AiiDA, including in prose.

This changes docstrings and comments only. No behaviour, port, help text or
spec requirement changes, so the `specs/` deltas are unaffected. The port help
strings of Decision 1 stay as written.

## Risks / Trade-offs

- [Each read copies every input file to a temporary directory] → Accepted. The
  copy is streamed and deleted on exit. PythonJob staging also copies.
- [Euphonic's Phonopy reader `print`s progress] → Upstream behaviour; it appears
  in daemon logs. This package's no-`print` rule (ruff T20) applies only to its
  own code.
- [The broad `TypeError`/`KeyError` catch could hide a bug in our call] →
  Positive tests on every valid input set (Decision 4).
- [aiida-core infers calcfunction port types from annotations, and
  `SinglefileData | None` with `from __future__ import annotations` could be
  rejected] → The module already uses future annotations with
  `read_castep_force_constants`. If the `| None` form fails at import, drop the
  annotations on the optional parameters and keep the defaults of `None`.
  aiida-core treats a parameter with a `None` default as an optional port.

## Migration Plan

The change only adds inputs. No data migration is needed. Existing `castep_file`
and `node` callers, and stored processes, are unaffected. Rolling back removes
the namespace.
