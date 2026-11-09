# Proposal: Phonopy files as a force-constants source for workflows

## Why

Phonopy output can be read into force constants at library level — the
`read_force_constants_from_phonopy` operation, the `prepare_read_phonopy_inputs`
PythonJob builder and `ForceConstantsData.from_phonopy` — but no workflow
accepts Phonopy files. `ForceConstantsWorkChain`, which resolves the force
constants for every force-constants workflow, takes only a CASTEP file or a
prepared `ForceConstantsData` node. A caller holding `phonopy.yaml` and
`force_constants.hdf5` must therefore run a separate read step and pass its
result in as `node`. That is an extra launch with its own provenance root, and it
is the one source format where callers (including a downstream AiiDAlab
application that uploads files as `SinglefileData`) cannot hand files straight to
the workflow.

HDF5 is the format Phonopy writes for force constants by default on all but small
systems, and Euphonic's Phonopy reader already reads it. This plugin neither tests
nor documents that path.

## What Changes

- Add a `phonopy` input namespace to `ForceConstantsWorkChain`, holding
  `SinglefileData` ports `summary` (`phonopy.yaml`, required within the
  namespace), `force_constants` (optional; HDF5 or text `FORCE_CONSTANTS`) and
  `born` (optional). Every force-constants workflow exposes the namespace
  automatically as `force_constants.phonopy`.
- Widen the source rule from "exactly one of `castep_file` / `node`" to "exactly
  one of `castep_file` / `phonopy` / `node`", still validated before any
  computation.
- Read the Phonopy files in-process with a calcfunction, matching the existing
  CASTEP source: the read is recorded as a calculation linking the files to the
  output `ForceConstantsData`, and an unreadable input set ends the workflow with
  the existing read-failure exit code (410).
- Bundle an HDF5 Phonopy NaCl sample from Euphonic's test data and use it to
  cover the library-level Phonopy reader as well as the new workflow source. The
  reader already supports HDF5; this change records and tests that support rather
  than adding it.
- Update the Phonopy gallery example so that it hands the files straight to the
  workflows.
- Label `prepare_read_phonopy_inputs` as a demonstration of PythonJob file
  staging, as `prepare_read_force_constants_inputs` already is for CASTEP. Once
  workflows read Phonopy files in-process, no workflow uses it, and it is likely
  to be removed before version 1.0. It stays, unchanged in behaviour, for now.

## Capabilities

### New Capabilities

*(None)*

### Modified Capabilities

- `phonon-workflows`: force-constants workflows and `ForceConstantsWorkChain`
  accept a third source, a Phonopy file set, grouped under a `phonopy` namespace.
  The "exactly one source" rule covers all three.
- `phonon-operations`: the Phonopy reader requirement states that the
  force-constants file may be HDF5 or text. This documents existing behaviour.
- `documentation`: the Phonopy example supplies Phonopy files directly to the
  workflows.

## Non-goals

- Exposing Euphonic's `fc_format` override. The format is inferred from the
  stored file name's extension, which `SinglefileData` preserves. See design.md.
- Restricting the `force_constants` port to HDF5. Both formats go through the
  same Euphonic call, so a restriction would add a check and remove nothing.
- Avoiding the temporary copy of each file during the read. AiiDA exposes
  repository content as a path only by copying it. See design.md.
- Changing the behaviour of, or removing, `prepare_read_phonopy_inputs` and
  `read_force_constants_from_phonopy`. Only their docstrings change. Removal is
  deferred to a later change, before version 1.0. This is separate from the
  `node` input, which accepts a `ForceConstantsData` built by any means.
- Other Phonopy inputs, such as `FORCE_SETS` or a displacement dataset needing
  Phonopy itself to compute force constants.
- Changing exit-code numbers. The calcfunction uses 300 and the workflow uses 410,
  as for CASTEP.

## Impact

- `src/aiida_pythonjob_ins/workflows/force_constants.py`: new
  `read_phonopy_force_constants` calcfunction; `phonopy` namespace, widened
  validator and outline branch on `ForceConstantsWorkChain`.
- `src/aiida_pythonjob_ins/workflows/base.py`: no change
  (`expose_inputs` picks up the namespace).
- `src/aiida_pythonjob_ins/operations.py`, `pythonjobs.py`: docstring note on
  HDF5 only.
- Dispersion, DOS and TOSCA-from-force-constants workflows: gain
  `force_constants.phonopy.*` inputs with no code change. Existing callers are
  unaffected, because the change only adds inputs.
- `tests/data/phonopy/`: new NaCl HDF5 sample set with provenance recorded in
  `tests/data/README.md`.
- `tests/`: workflow and operation tests for the Phonopy source and HDF5 input.
- `tests/conftest.py`: a `phonopy_hdf5_dir` fixture.
- `docs/source/tutorials/plot_phonopy_bands_and_dos.py`,
  `docs/source/workflows.rst`, `README.md`, `CHANGELOG.md`.
- Dependencies: none new. `h5py` already arrives via `euphonic[phonopy-reader]`.
