# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- The PyPI distribution name `aiida-alc-ins`. The import package
  `aiida_pythonjob_ins` and the entry-point names (`pythonjob_ins.*`) keep their
  current names until 0.2, when they are renamed to `aiida_alc_ins` and
  `alc_ins`.
- `aiida_pythonjob_ins.__version__`, read from the installed distribution's
  metadata. AiiDA records it as the plugin version in the provenance of each
  process.
- `ForceConstantsWorkChain`, a public, standalone workflow registered as the
  `pythonjob_ins.force_constants` entry point. It resolves exactly one
  force-constants source into a `force_constants` output:
  - a CASTEP `castep_file` (`SinglefileData`);
  - Phonopy files in a `phonopy` namespace: `summary` (`phonopy.yaml`, required
    within the namespace), optional `force_constants` (HDF5 or Phonopy text
    `FORCE_CONSTANTS`) and optional `born`;
  - a prepared `node` (`ForceConstantsData`).

  Files are read in-process by a calcfunction. The workflow dispatches no jobs,
  takes no `Code`, and ends with `410 ERROR_READ_FAILED` if a file is unreadable.
- `DispersionWorkChain`, `DosWorkChain` and `ToscaFromForceConstantsWorkChain`
  accept Phonopy files directly, as `force_constants.phonopy`. Previously they
  needed a `ForceConstantsData` node made in a separate step.
- Bundled sample data `tests/data/phonopy/NaCl_hdf5/`: NaCl Phonopy output in
  HDF5 form, from Euphonic's test suite. HDF5 force constants were already
  readable; this adds test and documentation coverage.

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
  file staging. Workflows read Phonopy files in-process through
  `force_constants.phonopy`, so no workflow uses this builder, and it is likely to
  be removed before version 1.0. Its behaviour is unchanged.

- Workflow pages now render each WorkChain's docstring as formatted
  reStructuredText, so exit-code lists, inline literals and cross-references
  between workflows appear as rendered documentation rather than raw source.

### Removed

- The abstract `ForceConstantsWorkChain` base class and its
  `should_read_castep`, `read_force_constants` and `assign_force_constants`
  outline steps. The name now refers to the standalone workflow added above.

[Unreleased]: https://github.com/stfc/aiida-alc-ins/tree/HEAD
