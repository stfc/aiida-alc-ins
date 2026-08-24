## 1. Dependencies and sample data

- [x] 1.1 Add `abinslib==0.1.*` and `resins~=0.1.0` to `pyproject.toml`
      dependencies, each with a rationale comment matching the project's
      existing dependency-comment convention (Decision 11).
- [x] 1.2 Vendor `ethanol_qpoint_phonon_modes.json` from `abINS_lib`'s test data
      into `tests/data/`, with a short note recording its origin (upstream
      path, commit/release) and licence (Decision 13).
- [x] 1.3 Run `uv sync` and confirm `abinslib` and `resins` import successfully
      in the project environment.

## 2. Serializer registry robustness

- [x] 2.1 Add a `_serializer_key(cls)` helper in `serialization.py` computing
      `f"{cls.__module__}.{cls.__name__}"`, matching how `aiida-pythonjob`
      builds its lookup key (Decision 10).
- [x] 2.2 Convert the three existing `EUPHONIC_SERIALIZERS` entries
      (`ForceConstants`, `QpointPhononModes`, `Spectrum1D`) to derive their keys
      from the imported classes via `_serializer_key` instead of hand-written
      strings, preserving behaviour.
- [x] 2.3 Add a test asserting every `EUPHONIC_SERIALIZERS` key resolves to an
      importable class matching that key (plugin-packaging: "Every registry key
      names an importable class").

## 3. `Spectrum1DCollection` \u2194 `XyData` conversions

- [x] 3.1 Add a labelling helper in `conversions.py` that derives a concise,
      human-readable label from a spectrum line's metadata, using only the keys
      that vary across the collection's lines (Decision 3).
- [x] 3.2 Add `spectrum_collection_to_xydata` in `conversions.py`: bin centres as
      the x array, one y array per line named via the labelling helper, and
      node attributes `spectrum_metadata` (common metadata) and
      `spectrum_line_data` (per-line metadata) recording the full collection
      metadata losslessly (Decisions 3, 4).
- [x] 3.3 Add `xydata_to_spectrum_collection` in `conversions.py`, the reverse
      conversion, reconstructing a `Spectrum1DCollection` with `line_data`
      metadata from the node's attributes.
- [x] 3.4 Register the new `Spectrum1DCollection` serializer in
      `EUPHONIC_SERIALIZERS` (via `_serializer_key`, per task 2.1), wrapping
      `spectrum_collection_to_xydata`.
- [x] 3.5 Add round-trip tests: converting a collection to `XyData` and back
      preserves line count, x/y values, and both common and per-line metadata;
      grouping the recovered collection by a metadata key matches grouping the
      original.
- [x] 3.6 Add a labelling test: lines whose metadata differs only in one key
      produce distinct, readable labels reflecting that key's value.

## 4. TOSCA scientific operations (`tosca-spectra` capability)

- [x] 4.1 Add a function computing thermal displacements from modes at a given
      temperature, wrapping `abinslib.displacements.Displacements.from_modes`
      and `.to_atomic_displacements`.
- [x] 4.2 Add a function computing the indirect-geometry Q\u00b2 kinematics for a
      scattering angle and final energy, for both per-mode and per-bin
      evaluation, wrapping `abinslib.util.calculate_indirect_q2`.
- [x] 4.3 Add a function building the TOSCA energy axis: reuse
      `default_energy_bins` on the fundamental frequencies scaled by the
      maximum quantum order, then clip to a caller-supplied maximum energy,
      honouring a caller-supplied `energy_unit` (Decision 7).
- [x] 4.4 Add the top-level scattering-intensity operation combining fundamental
      and combination-mode intensities (wrapping
      `calculate_almost_isotropic_incoherent_spectra` and
      `mantid_like_combination_spectra`) across one or more scattering angles,
      tagging every resulting line with `atom_symbol`, `quantum_order` and
      `detector_angle` metadata (Decisions 8, 9).
- [x] 4.5 Add a function applying a named `resins` resolution model to a
      spectrum or collection (Decision 9).
- [x] 4.6 Add unit tests for each operation asserting equivalence with direct
      `abinslib`/`resins` calls on the same inputs.
- [x] 4.7 Add a test confirming the energy axis reaches the highest
      combination-mode frequency when that lies below the instrument maximum,
      and is clipped at the instrument maximum otherwise (both directions of
      Decision 7).
- [x] 4.8 Add a test confirming two different scattering angles applied to the
      same modes give different Q\u00b2 values and different intensities.
- [x] 4.9 Add a test confirming resolution broadening commutes with summation:
      broadening each line then summing equals summing then broadening, to
      numerical precision.

## 5. PythonJob builder

- [x] 5.1 Add a `prepare_tosca_spectrum_inputs` builder in `pythonjobs.py`
      wrapping the operation from task 4.4 as a PythonJob, following the
      pattern of `prepare_dos_inputs`.
- [x] 5.2 Add a test launching the builder as a real `PythonJob` and asserting
      the result is an `XyData` with one line per contributing atom, quantum
      order and detector angle, each finite and labelled
      (pythonjob-execution: "A scattering-intensity job produces a multi-line
      spectrum node").

## 6. `ToscaFromModesWorkChain`

- [x] 6.1 Create `workflows/tosca.py`; define `ToscaFromModesWorkChain` with
      inputs `modes` (`QpointPhononModesData`), `temperature`,
      `energy_spacing`, `energy_max`, `energy_unit`, `detector_angles`,
      `final_energy`, `resolution_model`, `group_by` and `code`, with defaults
      per Decisions 7\u20139.
- [x] 6.2 Add the `compute_intensities` step submitting the task 5.1 builder as
      a `PythonJob`.
- [x] 6.3 Add the `group_spectra` `calcfunction`: convert the intensity result
      to a collection, call `collection.group_by(*group_by)`, convert back
      (Decision 6).
- [x] 6.4 Add the `broaden_spectra` `calcfunction` applying the resolution model
      (task 4.5) to the grouped result (Decision 5).
- [x] 6.5 Wire the outline `compute_intensities -> group_spectra ->
      broaden_spectra -> finalize`; output `components` (the full,
      ungrouped line set from `compute_intensities`) and `spectrum` (grouped
      and broadened).
- [x] 6.6 Add exit code `400 ERROR_SUB_PROCESS_FAILED` for a failed PythonJob
      step, documented in the class docstring (Decision 12).
- [x] 6.7 Add workflow tests: a successful run produces a valid `components`
      output and a valid `spectrum` output; different `group_by` values change
      the number of lines in `spectrum` accordingly; an empty `group_by`
      yields a single total line; the sum of the grouped lines equals the sum
      of the ungrouped lines.
- [x] 6.8 Add a test confirming `ToscaFromModesWorkChain`'s declared inputs
      contain no q-point sampling parameter.
- [x] 6.9 Add a caching test: running the workflow twice with identical inputs
      except `group_by`, with caching enabled, reuses the `compute_intensities`
      result (assert via `is_created_from_cache`) while still producing the
      newly grouped `spectrum`.

## 7. `ToscaFromForceConstantsWorkChain`

- [x] 7.1 Define `ToscaFromForceConstantsWorkChain` in `workflows/tosca.py`,
      subclassing `ForceConstantsWorkChain`; add a `q_spacing` input; call
      `expose_inputs(ToscaFromModesWorkChain, namespace="spectrum",
      exclude=("modes", "code"))` (Decision 1).
- [x] 7.2 Add an `interpolate_modes` step producing a `QpointPhononModesData`
      from `self.ctx.force_constants` and `q_spacing`, reusing the existing
      interpolation operation/builder.
- [x] 7.3 Add a `compute_spectrum` step submitting `ToscaFromModesWorkChain`
      with the exposed `spectrum` namespace inputs, the interpolated modes,
      and the inherited `code`.
- [x] 7.4 Call `expose_outputs(ToscaFromModesWorkChain)`; in the finalize step,
      call `self.out_many(self.exposed_outputs(...))` from the sub-workchain's
      results.
- [x] 7.5 Add exit code `401 ERROR_SPECTRUM_WORKCHAIN_FAILED` for a failed
      sub-workchain, distinct from the inherited `400`; document both exit
      codes in the class docstring (Decision 12).
- [x] 7.6 Add workflow tests: the chain accepts either a CASTEP file or a
      `ForceConstantsData` node per the inherited validator; its outputs match
      what `ToscaFromModesWorkChain` alone produces for the same interpolated
      modes; the sub-workchain appears as a called node in the provenance
      graph.
- [x] 7.7 Add a test that a failure of the nested `ToscaFromModesWorkChain`
      surfaces as `401`, distinguishable from a `400` raised by this chain's
      own force-constants step.

## 8. Packaging and entry points

- [x] 8.1 Register `pythonjob_ins.tosca_from_modes` \u2192 `ToscaFromModesWorkChain`
      and `pythonjob_ins.tosca_from_force_constants` \u2192
      `ToscaFromForceConstantsWorkChain` under
      `[project.entry-points."aiida.workflows"]` in `pyproject.toml`.
- [x] 8.2 Extend `tests/test_entry_points.py` to cover both new entry points,
      following the existing pattern for `pythonjob_ins.dos` and
      `pythonjob_ins.dispersion`.
- [x] 8.3 Reinstall (`uv sync`) so the new entry points are discoverable, and
      confirm both resolve through AiiDA's workflow factory.

## 9. Documentation

- [x] 9.1 Add `docs/source/tutorials/plot_tosca_from_modes.py`: load the ethanol
      modes via `QpointPhononModesData.from_json_file` and `DataFactory`, run
      `ToscaFromModesWorkChain` via `WorkflowFactory`, and plot the spectrum
      grouped by quantum order and then by atom symbol, plus the provenance
      graph.
- [x] 9.2 In that tutorial, enable caching explicitly
      (`aiida.manage.enable_caching`) before re-running with a different
      `group_by`, and assert the intensity step's result
      `is_created_from_cache` so a caching regression fails the docs build.
- [x] 9.3 Add `docs/source/tutorials/plot_tosca_from_force_constants.py`: run
      `ToscaFromForceConstantsWorkChain` from the bundled quartz force
      constants, plot the resulting spectrum and the provenance graph showing
      the nested sub-workchain, and state on the page that quartz is a
      legitimate but atypical TOSCA sample.
- [x] 9.5 Add `.. aiida-workchain::` entries for `ToscaFromModesWorkChain` and
      `ToscaFromForceConstantsWorkChain` to `docs/source/workflows.rst`, and
      adjust its introductory text so it no longer implies every listed
      workflow accepts a `castep_file`/`force_constants` pair.
- [x] 9.6 Update the README's workflow summary to mention the two new TOSCA
      workflows, rephrasing the "both accept..." framing so it still holds
      once a modes-only workflow is included.
- [x] 9.7 Build the documentation (`uv run --group doc make -C docs html`) and
      confirm both new examples execute cleanly with no warnings.

## 10. Final verification

- [x] 10.1 Run the full test suite (`uv run pytest`) and confirm every test
      passes, including the new TOSCA modules.
- [x] 10.2 Run `uv run ruff check` and `uv run ruff format --check`, fixing any
      issues.
- [x] 10.3 Run `openspec validate abinslib-workflow --strict` and confirm it
      passes.

## Deferred to a follow-up change

Not tracked as tasks here; recorded in `proposal.md` and `design.md` — Open
Questions.

- **Replace the quartz sample in `plot_tosca_from_force_constants.py`** with a
  hydrogenous molecular crystal. Needs a force-constants dataset that is
  redistributable under a GPL-3-or-later-compatible licence, small enough to
  vendor, and citable to a pinned upstream revision. Deferred because none was to
  hand and sourcing one is self-contained. The page meanwhile declares itself
  unrepresentative, which is what the `documentation` capability asks of it, so
  no requirement is left unmet.
- **Report two `abinslib` 0.1 defects upstream**, both in
  `mantid_like_combination_spectra`: the O(N²) accumulation by repeated
  `Spectrum1DCollection.__add__` (fixed by collecting the lines and making one
  `from_spectra(..., unsafe=True)` call), and the discarded return value of its
  own `group_by("atom_index")`. When the latter is released, the compensating
  grouping in `calculate_tosca_spectrum` can be simplified — the code comment
  there says so.
