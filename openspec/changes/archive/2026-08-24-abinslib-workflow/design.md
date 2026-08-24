## Context

See `proposal.md` — Why, for the motivation. This section records only the
constraints that shape the approach.

**The reference pipeline.** `abinslib`'s TOSCA tutorial
(<https://isisneutronmuon.github.io/abINS_lib/auto_examples/plot_tosca.html>) is
the calculation being wrapped. It runs: modes → `Displacements.from_modes` →
`to_atomic_displacements` → `calculate_indirect_q2` (per mode *and* per bin) →
`calculate_almost_isotropic_incoherent_spectra` + `mantid_like_combination_spectra`
→ add → `resins` broadening.

**What `abinslib` returns.** Both spectrum functions return a Euphonic
`Spectrum1DCollection` whose per-line metadata comes from `iter_atom_info` plus a
quantum-order tag:

```python
metadata = {
    "method": "almost-isotropic incoherent",  # common to all lines
    "line_data": [  # one dict per line
        {"atom_index": 0, "atom_symbol": "C", "mass": "12.0107", "quantum_order": 1},
        ...,
    ],
}
```

Every value is a string or an integer, which matters for storage: AiiDA node
attributes accept exactly this kind of JSON-serialisable scalar.

**TOSCA's measurable range.** The instrument can reach roughly 8000 cm⁻¹, but
results are conventionally examined only up to about 4000 cm⁻¹. TOSCA also has two
detector banks, backward at 135° and forward at 45°, each with its own kinematic
constraint; the reference example computes only the backward bank.

**What `XyData` can hold.** Inspecting `aiida-core`, `XyData.set_y` writes the
arrays into the repository under *positional* names (`y_array_0`, `y_array_1`, …)
and stores the caller's names and units as the node attributes `y_names` and
`y_units`. `ArrayData.set_array`'s `[0-9a-zA-Z_]` charset restriction therefore
never applies to a y-array *name*; `XyData._arrayandname_validator` only requires
`isinstance(name, str)`. `get_y()` returns `list[tuple[name, array, unit]]`. The
one hard constraint is that every y array must have the same shape as x.

**Existing structure this must fit.** `operations.py` is AiiDA-free and shipped
by reference into the remote environment; `pythonjobs.py` builds PythonJob inputs;
`serialization.py` maps Euphonic classes to node constructors by dotted path;
`conversions.py` holds plain (non-calcfunction) converters; `workflows/base.py`
provides `ForceConstantsWorkChain`, subclassed by `DosWorkChain` and
`DispersionWorkChain`. The `dos-clipping` change added a reusable
`default_energy_bins(frequencies, spacing)` helper.

**Version skew in the dependency.** `abinslib`'s `main` branch has already moved
on from 0.1: the released `calculate_almost_isotropic_incoherent_spectra` takes
`apply_cross_section=True`, while `main` has removed it in favour of a separate
`apply_weights`. This is a concrete instance of the instability that motivates the
narrow pin, and a reason to code against the installed 0.1 release rather than the
published source tree.

## Goals / Non-Goals

**Goals:**

- Keep the TOSCA calculation itself in the AiiDA-free `operations.py` layer, so it
  is unit-testable and shippable to a remote environment like every other
  operation.
- Make the two workflows differ *only* in how modes are obtained, with no
  duplicated spectrum logic.
- Make regrouping and re-broadening cheap on a second run, by placing the
  expensive intensity calculation behind its own cacheable process node.
- Round-trip `Spectrum1DCollection` through `XyData` losslessly enough that
  Euphonic's own `group_by`/`sum` can be applied to data read back from the graph.
- Keep the conversion layer instrument-agnostic, so a later instrument reuses it
  untouched.

**Non-Goals:**

- Optimising the intensity calculation itself; `abinslib` owns that.
- Preserving the histogram/bin-edge nature of spectra through `XyData` (see
  Decision 4).
- Generalising instrument geometry (see `proposal.md` — Non-goals).

## Decisions

### 1. Two WorkChains: inherit for the source, compose for the calculation

`ToscaFromForceConstantsWorkChain` subclasses `ForceConstantsWorkChain` and
composes `ToscaFromModesWorkChain` through AiiDA's exposed-input machinery
([Workflows: exposing inputs and outputs](https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/workflows/usage.html#exposing-inputs-and-outputs)):

```python
spec.expose_inputs(
    ToscaFromModesWorkChain, namespace="spectrum", exclude=("modes", "code")
)
...
inputs = AttributeDict(
    self.exposed_inputs(ToscaFromModesWorkChain, namespace="spectrum")
)
inputs.modes = self.ctx.modes
inputs.code = self.inputs.code
...
spec.expose_outputs(ToscaFromModesWorkChain)
self.out_many(self.exposed_outputs(self.ctx.spectrum, ToscaFromModesWorkChain))
```

`modes` is excluded because the chain produces it internally; `code` is excluded
because `ForceConstantsWorkChain` already declares it at the top level and
duplicating it would let a user set two conflicting codes.

This mirrors `PwBandsWorkChain`, which exposes `PwBaseWorkChain` twice under `scf`
and `bands` namespaces rather than reimplementing an SCF
([aiida-quantumespresso](https://github.com/aiidateam/aiida-quantumespresso/blob/main/src/aiida_quantumespresso/workflows/pw/bands.py)).

*Rejected — one chain accepting either input.* `q_spacing` would be required for
one input and meaningless for the other, which a flat process spec cannot express.
The general rule, worth recording because the codebase already contains a
legitimate either/or port: **mutually exclusive inputs are acceptable when they
are interchangeable sources of the same object and change nothing else about the
required input set.** `castep_file | force_constants` satisfies that;
`force_constants | modes` does not.

*Rejected — composing `ForceConstantsWorkChain` too, for symmetry.* It is
currently a base contributing an outline fragment and no outputs, so composing it
would first require giving it a complete outline and a `force_constants` output.
That is a worthwhile follow-up but not a prerequisite, and doing it here would
also churn `DosWorkChain` and `DispersionWorkChain`.

*Rejected — `ToscaBaseWorkChain`/`ToscaWorkChain` naming.* `Base` marks a chain
offered as the recommended starting point for others to build **on top of**. For
DFT codes that usually means error handling, but it covers input normalisation
too — mapping high-throughput-friendly names onto lower-level choices, for
instance. Neither sense applies here: `ToscaFromModesWorkChain` is designed to be
*composed*, not subclassed, and no descendants are planned. The name would also
say nothing about what actually distinguishes the pair, which is the input data
(Decision 2).

### 2. `ToscaFromModesWorkChain` requires a modes *node*, and needs no new code

The chain takes a `QpointPhononModesData` input and nothing else as a source. No
reader operation, no file port, no new constructor: `EuphonicJSONData` already
provides `from_json_file`, so `QpointPhononModesData.from_json_file(path)` works
today and is already covered by the `euphonic-data-nodes` requirement
"Rebuilding a node from a previously written Euphonic JSON file".

**Requiring a node at the core is the architectural point, not a shortcut.** The
node-taking chain is the stable centre; any convenience that ingests files is a
chain composed *around* it. `ToscaFromForceConstantsWorkChain` is already an
instance of exactly that shape, and a later file-loading chain aimed at a GUI would
be another. Keeping the core narrow is what makes those compositions possible
without revisiting it.

*Rejected — a `read_modes_from_json` operation, run either inside the chain (as
`castep_file` is) or standalone before it (as `prepare_read_phonopy_inputs` is).*
Both are established patterns in this codebase, so the objection is not
unfamiliarity. It is that the step would transform nothing. `from_json_file`
stores the file **byte-for-byte** in the node repository:

```python
node.base.repository.put_object_from_file(str(filepath), cls._filename)
```

A read job would therefore parse that JSON into a `QpointPhononModes`, return it,
and have the serializer write it back out as a node containing the same bytes — a
process node recording a round trip with no information content. Contrast the
CASTEP and Phonopy force-constants readers, where a genuine conversion happens
(binary `.castep_bin`, or a multi-file Phonopy set, into a Euphonic object) and
recording it captures something real.

The principle worth carrying forward: **a reading step earns its place in the
provenance graph when it performs a format conversion; deserialising our own
storage format does not.**

*Deferred — modes from calculator output.* Euphonic also reads modes from formats
that *are* genuine conversions: `QpointPhononModes.from_castep` for a CASTEP
`.phonon` file and `QpointPhononModes.from_phonopy` for a Phonopy `band.yaml`
set. Those would justify reader operations and file-ingest chains on exactly the
same terms as the existing force-constants support, and they compose around this
chain without altering it. Out of scope here, where the goal is a clean,
executable demonstrator.

> **Consequence for the proposal's Capabilities list:** `phonon-operations` is *not*
> modified after all, and neither is `euphonic-data-nodes` — the constructor and
> its scenario already exist. Separately, `pythonjob-execution` *is* modified,
> because its requirement enumerates the input builders and this change adds one
> for the TOSCA intensity job.

### 3. Metadata travels in node attributes; `y_names` carry plot labels

The forward conversion writes:

- `y_names` — one human-readable label per line, produced by the labelling helper
  (`"C (order 1)"`, `"H"`, `"Order 2"`, … depending on which keys vary);
- `y_units`, `x` — as the existing `spectrum1d_to_xydata` does;
- node attributes `spectrum_metadata` (the collection's common metadata) and
  `spectrum_line_data` (the list of per-line dicts).

The reverse conversion reads the attributes back and rebuilds
`metadata={**common, "line_data": [...]}`.

These are ordinary node attributes set on a plain `XyData`, not values packed into
an existing `XyData` field. AiiDA imposes no attribute schema on `Data` nodes: any
JSON-serialisable value may be attached under any key before the node is stored.
Verified on a stored node, the attribute set reads:

```python
{
    "x_name": "energy",
    "x_units": "meV",
    "array|x_array": [3],
    "array|y_array_0": [3],
    "y_names": ["C (order 1)"],
    "y_units": ["1/meV"],
    "spectrum_metadata": {"method": "almost-isotropic incoherent"},
    "spectrum_line_data": [
        {"atom_index": 0, "atom_symbol": "C", "mass": "12.0107", "quantum_order": 1}
    ],
}
```

The new keys sit alongside `XyData`'s own without collision — its arrays are
namespaced with an `array|` prefix — and become immutable once the node is stored
(`ModificationNotAllowed`), which is the behaviour provenance requires.

Rationale: the metadata is a handful of JSON scalars per line, which is precisely
what AiiDA attributes are for — small, structured, and *queryable*, so a
`QueryBuilder` can later select spectra by method, quantum order or detector
angle. Bulk numerical data stays in the repository, consistent with the
`euphonic-data-nodes` capability's split. Labels in `y_names` mean
`for name, y, unit in xy.get_y()` is directly plottable with no metadata parsing —
the labelling helper does its work on the *write* side, once, rather than in every
consumer.

*Rejected — encoding metadata as JSON into `y_names`.* Legal (the validator only
demands `str`), but it would put an opaque blob where AiiDA and every plotting
convenience expect a short label, and would make the node's own repr unreadable.

*Rejected — a separate `Dict` node beside the `XyData`.* Two nodes that must be
kept together is a weaker guarantee than one node that is self-describing, and it
complicates the serializer, which must return a single node.

*Rejected — a bespoke `SpectrumCollectionData` class.* Ruled out in the proposal;
`XyData` is consumable by existing AiiDA tooling and this change is about
demonstrating native-type interoperability.

### 4. The x axis is stored as bin centres; edges are not preserved

`XyData` requires x and y to have the same shape, while a histogram-like
`Spectrum1DCollection` holds `n+1` bin edges. The conversion stores
`get_bin_centres()`, as `spectrum1d_to_xydata` already does, so a round-tripped
collection is a point spectrum rather than a histogram.

This is sufficient for everything the workflow does: `group_by` and `sum` operate
on `y_data` and carry the x axis through unchanged, and the reference example
performs its resolution broadening on bin *centres*
(`res.broaden(points=x[:, None], data=y, mesh=x)`).

*Rejected — storing edges in an extra array on the same node.* `XyData` permits
extra arrays via `set_array`, so this would work and would be lossless, but it
adds a shape convention that nothing in this change needs, and a consumer reading
`get_x()`/`get_y()` would not see it. Revisit if a later use requires exact
rebinning.

### 5. Three provenance steps, split by cost and by which input changes them

`ToscaFromModesWorkChain`'s outline:

| Step | Kind | Produces |
| --- | --- | --- |
| `compute_intensities` | PythonJob | full line set, one line per atom × quantum order |
| `group_spectra` | `calcfunction` | grouped/summed line set |
| `broaden_spectra` | `calcfunction` | resolution-broadened result |

Outputs: `components` (the full line set) and `spectrum` (grouped and broadened).
The intermediate grouped node is reachable through the calcfunction in the graph.

The split is chosen so that each step is invalidated by a *different* input. With
[caching](https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/provenance/caching.html)
enabled, changing `group_by` reuses the intensity calculation, and changing the
resolution model reuses both the intensities and the grouping. Because the split
lives in the modes chain, it applies equally when that chain is nested.

Broadening *after* summation is exact, not an approximation: the resolution
operator is linear in the spectrum values, so `broaden(Σ yᵢ) = Σ broaden(yᵢ)`.
Doing it last also means it is applied to the fewest lines.

*Rejected — broadening inside the PythonJob.* It is where the reference example
does it, but it would make a change of resolution model invalidate the expensive
step, destroying the property this design exists to demonstrate.

*Rejected — one calcfunction doing both.* Cheaper to write, but then the two
independent knobs share one cache entry.

*Note on the cost of this choice:* running broadening as a calcfunction means
`resins` must be importable in the *local* environment, not only in the remote job
environment. It is a declared dependency, so this is a documented consequence
rather than a hidden one.

*Rejected — `pyfunction` instead of `calcfunction` for the two cheap steps.*
`aiida-pythonjob`'s `PyFunction` declares `CalcFunctionNode` as its `_node_class`,
so provenance shape and caching behaviour are identical either way; the difference
is only at the boundary. A `pyfunction` accepts and returns plain Python objects,
converting them through the same serializer registry as a `PythonJob`, which would
remove the explicit conversion calls from the wrapper body.

Two things weigh against it. First, the decorator imports `aiida_pythonjob`, so a
decorated function cannot live in `operations.py`, whose import chain must stay
AiiDA-free. The scientific function lives there undecorated either way — only the
thin workflow-side wrapper differs — so the hoped-for simplification does not
materialise. Second, `pyfunction` would need a deserializer keyed on
`XyData`, and `XyData` is already the density-of-states output type holding a
`Spectrum1D`. A single node-type-keyed mapping would apply to every `XyData` input
to every job we launch, and an `XyData` cannot declare which Euphonic type produced
it except through the attributes written by Decision 3. That is an ambiguity
introduced into a shared registry in exchange for a few lines in one function.

The `calcfunction` form is four lines with the conversions written out, and matches
the existing parent-side precedent in this codebase. The choice is reversible at
low cost if the balance changes.

### 6. Grouping keys are an `orm.List`; empty means "total"

`group_by` is declared as `orm.List` with `default=lambda: orm.List(list=[])`, and
the grouping calcfunction passes its contents straight through:
`collection.group_by(*keys)`.

No special case is needed for the empty list. Euphonic's `group_by` with no keys
maps every line to the same empty grouping tuple, yielding a single summed line —
and, unlike `sum()`, it returns a `Spectrum1DCollection` rather than a
`Spectrum1D`. Routing both cases through `group_by` therefore keeps the step's
return type uniform, so the conversion back to `XyData` has one path rather than
two:

```
group_by()               -> Spectrum1DCollection, 1 line   (the total)
group_by("atom_symbol")  -> Spectrum1DCollection, n lines
sum()                    -> Spectrum1D                     (not used)
```

Euphonic already defines the semantics for multiple keys (lines match only when
*all* key values agree) and for missing keys (treated as `None`), so no validation
logic is duplicated here.

Keys are not validated against the metadata at input time: a typo yields a single
group rather than an error. That is Euphonic's behaviour and second-guessing it
would couple the workflow to `abinslib`'s metadata vocabulary.

### 7. The energy axis is bounded by the instrument, then clipped to the data

Two bounds are in play and the axis takes the tighter one.

*From the instrument:* an `energy_max` input, defaulting to **4000 cm⁻¹** — the
range TOSCA results are conventionally examined over, comfortably inside the
~8000 cm⁻¹ the instrument can reach. Because the value is user-settable, the
smaller conventional bound is the better default: anyone needing the full range
says so, and everyone else avoids computing and storing bins they will not look
at.

*From the data:* `default_energy_bins` sized from the fundamental frequencies
scaled by the maximum quantum order. Sizing from the fundamentals alone would
silently truncate second-order intensity, which extends to roughly twice the
fundamental range:

```python
data_bins = default_energy_bins(modes.frequencies * max_quantum_order, spacing)
bins = data_bins[data_bins <= energy_max]
```

Clipping down when the spectrum does not reach `energy_max` avoids a long dead
tail on the plot for low-frequency systems, and costs nothing when it does not
apply. This reuses the padding and alignment rules settled in `dos-clipping`
rather than restating them.

*Units.* The TOSCA operations take `energy_spacing`, `energy_max` and
`final_energy` in an `energy_unit` defaulting to `"1/cm"`, unlike `DosWorkChain`
which works in meV. Wavenumbers are the working unit for this instrument and for
the reference example, and an instrument-native default is less error-prone than
making users convert 4000 cm⁻¹ to 495.9 meV. The parameter *names* stay consistent
with the existing chains; only the default unit differs, and it is explicit.
`energy_spacing` defaults to 10 cm⁻¹, matching the reference example's 201 bins
over 0–2000 cm⁻¹; AbINS itself uses 1 cm⁻¹, which is one input away.

*Rejected — the reference example's fixed `linspace(0, 2000, 201) cm⁻¹`.* Fine for
one known sample, wrong for a workflow that must adapt to its input.

*Rejected — defaulting to the full 8000 cm⁻¹.* Only preferable if the bound were
not user-settable; since it is, the conventional range is the better default.

### 8. Both detector banks are computed, and distinguished by metadata

`detector_angles` is a `List` input defaulting to `[135.0, 45.0]` degrees — TOSCA's
backward and forward banks — with a shared `final_energy` (32 cm⁻¹). Each angle
gets its own `calculate_indirect_q2` evaluation, and the resulting lines are tagged
with a `detector_angle` entry in their per-line metadata.

This needs no new combination machinery: `detector_angle` simply joins
`atom_symbol` and `quantum_order` as a groupable key. Grouping by it plots the
banks separately; omitting it sums them, which the default empty `group_by`
already does. The feature and the grouping mechanism reinforce each other, and the
tutorial gains a third, physically meaningful grouping to demonstrate.

Summing the two banks weights them equally, which is what Mantid-Abins does. It is
also the only defensible choice: the effective detector counts drift as detectors
are masked or recommissioned, so a fixed coverage weighting would encode a number
that is stale by the following week. Exactness here is not a realistic target, and
the per-bank lines stay available for anyone who has current coverage figures.

*Rejected — one angle per run.* Users would run the chain twice and combine the
results by hand, outside provenance, when the workflow can carry both through the
same graph.

*Rejected — a `detector_bank` enum (`"backward"`/`"forward"`) resolving to angles.*
Friendlier to read, but it introduces a second way to say the same thing, needs a
mapping table this change has no second instrument to validate against, and has no
answer for an arbitrary angle. Deferred with the rest of the generalisation; the
numeric `detector_angle` metadata key is what a later named-bank layer would map
onto.

### 9. Resolution model and temperature inputs

The resolution model is a string input defaulting to `"AbINS_v1"`, passed to
`Instrument.from_default("TOSCA").get_resolution_function(...)`.

Temperature is an `orm.Float` in kelvin defaulting to 10 K, a typical TOSCA base
temperature. The reference example uses 50 K; tests state their temperature
explicitly, so the default only affects convenience.

### 10. Serializer keys are derived from the classes, not hand-written

`serialization.py` gains an entry mapping `Spectrum1DCollection` to a
node-returning wrapper around the forward conversion. The immediate trap is that
`Spectrum1DCollection` does **not** live beside `Spectrum1D`: the existing entry
keys on `euphonic.spectra.base.Spectrum1D`, while the collection is in
`euphonic.spectra.collections`. A path guessed by analogy would be wrong.

The deeper problem is what happens when a key is wrong. `aiida-pythonjob` builds
its lookup key as:

```python
data_type = type(data)
ep_key = f"{data_type.__module__}.{data_type.__name__}"
if ep_key in serializers:
    ...
# otherwise: fall through to JsonableData, then PickledData
```

A stale key therefore does not raise — it falls through to `JsonableData`, and
because `Spectrum1DCollection` implements `to_dict`, that fallback *succeeds*. The
result is a silently wrong node type: a `JsonableData` where the workflow's output
port expects an `XyData`, with the failure surfacing somewhere unrelated.

String keys are the registry's contract and cannot be changed here, but they need
not be hand-written. The keys are derived from the imported classes using the same
expression `aiida-pythonjob` uses:

```python
def _serializer_key(cls: type) -> str:
    """Registry key exactly as aiida-pythonjob computes it for a runtime object."""
    return f"{cls.__module__}.{cls.__name__}"

EUPHONIC_SERIALIZERS = {
    _serializer_key(Spectrum1DCollection): (
        "aiida_pythonjob_ins.serialization.spectrum_collection_to_xydata_node"
    ),
    ...
}
```

A key then follows the class if Euphonic relocates it, provided the import in
`serialization.py` still resolves. The existing three entries are converted to the
same form: a one-line, behaviour-preserving change that removes a whole class of
silent breakage rather than fixing one instance of it.

Belt and braces, a test asserts that every registry key resolves to an importable
class, so an upstream move that our imports do not cover fails loudly in CI instead
of at runtime. If a future Euphonic release moves a class while we still support
the older location, both paths can be registered simultaneously — the registry is a
plain dict and duplicate targets cost nothing.

No deserializer is added: nothing takes a spectrum *into* a PythonJob.

### 11. Dependency pinning is a deliberate exception

`abinslib==0.1.*` and `resins~=0.1.0` are narrower than the `plugin-packaging`
capability prefers, which asks that upper caps be justified individually rather
than applied by habit. The justification here is explicit upstream instability:
`abinslib` is alpha with an announced API change, `resins`' own README advises
pinning to a specific minor version, and `abinslib` 0.1 already requires
`resins==0.1.0` exactly — so the effective constraint on `resins` comes from the
resolver regardless of what this package declares.

The cost is real: any co-installed plugin needing a different `resins` will
conflict. That is accepted for a proof-of-concept and recorded so it is revisited
when `abinslib` stabilises.

### 12. Exit codes

`ToscaFromModesWorkChain` reuses the established `400 ERROR_SUB_PROCESS_FAILED`
for a failed PythonJob. `ToscaFromForceConstantsWorkChain` adds
`401 ERROR_SPECTRUM_WORKCHAIN_FAILED` so that a failure in the nested chain is
distinguishable from a failure of its own force-constants step. Both are
documented in the class docstrings, per the convention established by
`reconcile-documentation-gaps`.

### 13. Bundled sample data

`ethanol_qpoint_phonon_modes.json` is vendored from `abINS_lib`'s test data into
`tests/data/`, with a short provenance note recording its origin, upstream path
and licence. Fetching it at build time is rejected: the `documentation` capability
requires examples to run from bundled data so the build stays offline and
reproducible.

## Risks / Trade-offs

- **`abinslib` 0.1 differs from its `main` branch** — the released
  `calculate_almost_isotropic_incoherent_spectra` takes `apply_cross_section=True`,
  while `main` has replaced it with a separate `apply_weights` step → code and
  tests target the installed 0.1 release, and the published source tree is read for
  understanding only, never copied. Moving to the `apply_weights` form is planned
  for whenever it is released, and is the natural trigger for lifting the pin.
- **Alpha pins constrain co-installed plugins** → accepted and documented in
  Decision 11, with a revisit trigger when `abinslib` reaches a stable API.
- **Broadening as a calcfunction makes `resins` a local runtime requirement** →
  it is a declared dependency; the alternative would forfeit the caching property.
- **Caching is off by default in AiiDA**, so the tutorial's second grouping would
  silently recompute and the demonstration would be vacuous → the example enables
  it explicitly with `aiida.manage.enable_caching` and asserts that the second run
  is `is_created_from_cache`, so a regression fails the docs build rather than
  passing quietly.
- **Metadata in attributes could grow** for a large crystal (one dict per atom per
  quantum order per detector angle) → bounded by that product, tens of entries for
  the sample systems; the numerical data stays in the repository where it belongs.
- **Summing detector banks weights them equally**, whereas the banks differ in
  detector coverage → matches Mantid-Abins, and effective detector counts drift
  with masking and recommissioning, so a fixed weighting would be stale rather than
  more accurate; per-bank lines remain available.
- **A silently stale serializer key would yield a `JsonableData` instead of an
  `XyData`**, because `aiida-pythonjob` falls back rather than raising and
  `Spectrum1DCollection` has a working `to_dict` → keys are derived from the
  imported classes (Decision 10) and a test asserts each one resolves.
- **Bin edges are lost through `XyData`** → acceptable for grouping, summing and
  broadening (Decision 4); revisit if exact rebinning is ever needed.
- **The quartz force-constants example is atypical for TOSCA** → valid physics but
  a weak illustration; replacement with a molecular-crystal dataset is deferred to
  a follow-up change, and the page declares its own unrepresentativeness as the
  `documentation` capability requires.
- **Two new gallery examples lengthen the docs build**, which already executes real
  workflows → the ethanol calculation is a single gamma-point dataset and the
  quartz grid is kept coarse. Coarser than physics alone would justify, in fact:
  `abinslib` 0.1's `mantid_like_combination_spectra` accumulates its per-q-point
  spectra by repeated `Spectrum1DCollection.__add__`, which revalidates every
  previously accumulated line's units on each iteration and so costs O(N²) in the
  q-point count — measured at 98% of the runtime. A 3x3x3 grid keeps the page to
  ~4 minutes where a converged grid took 25. Optimising this is out of scope (see
  `proposal.md` — Non-goals); the fix belongs upstream, where collecting the lines
  and making a single `from_spectra(..., unsafe=True)` call restores linear
  scaling.

## Migration Plan

Purely additive: no existing node type, workflow, entry point or output changes,
so there is no stored-data migration and no deprecation cycle. Rollback is a
revert plus removal of the two dependencies.

Suggested order, each step leaving the suite green:

1. Dependencies and the vendored ethanol data.
2. Conversions (forward, reverse, label) plus their round-trip tests — independent
   of `abinslib`, so they can land and be trusted first.
3. Serializer registration, including deriving the existing keys from their classes
   and the test that asserts each key resolves.
4. TOSCA operations in `operations.py`, tested against direct `abinslib` calls.
5. `pythonjobs.py` builder.
6. `ToscaFromModesWorkChain`, then `ToscaFromForceConstantsWorkChain`.
7. Entry points, then the two gallery examples.

## Open Questions

- **Which molecular-crystal force-constants dataset** replaces quartz in the
  `ToscaFromForceConstantsWorkChain` example. **Deferred to a follow-up change.**
  It changes no spec, interface or step — only the file and the example's prose —
  and the quartz page satisfies the `documentation` capability as it stands by
  declaring itself unrepresentative. The dataset must be redistributable under a
  licence compatible with GPL-3-or-later, small enough to vendor, and citable to a
  pinned upstream revision, as `tests/data/README.md` does for the ethanol modes.
- **Whether the grouped-but-unbroadened spectrum deserves a named output** rather
  than being reachable only through the graph. Deferrable: adding an output later
  is backward-compatible.
