# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `ForceConstantsWorkChain`, a public, standalone workflow registered as the
  `pythonjob_ins.force_constants` entry point. It resolves exactly one
  force-constants source -- a CASTEP `castep_file` (`SinglefileData`) or a
  prepared `node` (`ForceConstantsData`) -- into a `force_constants` output,
  dispatches no jobs and takes no `Code`. An unreadable file ends it with
  `410 ERROR_READ_FAILED`.
- `ForceConstantsWorkChain`, and so every force-constants workflow, accepts a
  `phonopy` input namespace: `summary` (`phonopy.yaml`, required within the
  namespace), optional `force_constants` (HDF5 or Phonopy text `FORCE_CONSTANTS`)
  and optional `born`. The files are read in-process by a calcfunction, and a
  failed read exits `410 ERROR_READ_FAILED`.
- Bundled sample data `tests/data/phonopy/NaCl_hdf5/`: NaCl Phonopy output in
  HDF5 form, from Euphonic's test suite.

### Changed

- **BREAKING**: In `DispersionWorkChain`, `DosWorkChain` and
  `ToscaFromForceConstantsWorkChain`, the force-constants source inputs move
  into a `force_constants` namespace whose ports are those of
  `ForceConstantsWorkChain`:

  ```python
  # before
  run(DispersionWorkChain, castep_file=f, ...)
  run(DispersionWorkChain, force_constants=fc_node, ...)
  # after
  run(DispersionWorkChain, force_constants={"castep_file": f}, ...)
  run(DispersionWorkChain, force_constants={"node": fc_node}, ...)
  ```

- **BREAKING**: These workflows now run `ForceConstantsWorkChain` as a
  sub-workflow for either source. When it fails (for example, an unreadable
  CASTEP file), they exit with `402 ERROR_SUB_PROCESS_FAILED_FORCE_CONSTANTS`
  instead of `400`; `400 ERROR_SUB_PROCESS_FAILED` now means only that one of
  their own `PythonJob` steps failed.
- **BREAKING**: These workflows no longer subclass `ForceConstantsWorkChain`.
  They combine two independent abstract bases, `FromForceConstantsWorkChain`
  (the force-constants source) and `JobDispatchWorkChain` (`code`/`options`
  handling). `ToscaFromModesWorkChain` subclasses only `JobDispatchWorkChain`.

- CASTEP files are read in-process by a calcfunction, recorded as its own
  `CalcFunctionNode` in the provenance graph, instead of by a dispatched
  `PythonJob`. This removes about 2.8 s of job overhead from a read that takes
  about 0.1 s. `prepare_read_force_constants_inputs` remains available as an
  example of `PythonJob` file staging.

- `prepare_read_phonopy_inputs` is documented as a demonstration of `PythonJob`
  file staging. Workflows read Phonopy files in-process through the `phonopy`
  source, so no workflow uses this builder, and it is likely to be removed before
  version 1.0. Its behaviour is unchanged.

- Workflow pages now render each WorkChain's docstring as formatted
  reStructuredText, so exit-code lists, inline literals and cross-references
  between workflows appear as rendered documentation rather than raw source.

### Removed

- The abstract `ForceConstantsWorkChain` base class and its
  `should_read_castep`, `read_force_constants` and `assign_force_constants`
  outline steps. The name now refers to the standalone workflow above.

[Unreleased]: https://github.com/ajjackson/aiida_pythonjob_ins/tree/HEAD
