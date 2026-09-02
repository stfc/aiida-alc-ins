# Agent Guidelines for `aiida-pythonjob-ins` (AGENTS.md)

This file defines runtime constraints, architectural invariants, and coding conventions for AI agents working in this repository.

---

## 1. Project Purpose & Exemplar Role

`aiida-pythonjob-ins` is an AiiDA plugin that executes inelastic neutron scattering (INS) and lattice dynamics Python libraries—specifically [Euphonic](https://euphonic.readthedocs.io), [abinslib](https://isisneutronmuon.github.io/abINS_lib/), and [resins](https://pace-neutrons.github.io/resins/)—using the [`aiida-pythonjob`](https://github.com/aiidateam/aiida-pythonjob) execution model instead of traditional command-line wrappers.

### Exemplar Quality & Documentation Style
This codebase is an **architectural exemplar and proof of concept** for future `aiida-pythonjob` plugins developed across the Ada Lovelace Centre (ALC) and STFC:
* **Clarity over cleverness**: Idiomatic AiiDA patterns, clean abstraction boundaries, and maintainability take precedence over rapid feature expansion.
* **Generous, well-cited comments**: Explain the *why* behind serialization choices, execution boundaries, and library adaptations. Code comments serve as reference material for developers implementing sibling `aiida-pythonjob` plugins.
* **Precise API boundaries**: Explain why operations are placed on one side of a `PythonJob` boundary vs. inside a parent-side `calcfunction`.

---

## 2. Architecture & Invariants

The repository enforces strict separation of concerns across distinct layers:

```
src/aiida_pythonjob_ins/
├── operations.py      # Pure Python scientific operations (AiiDA-free!)
├── pythonjobs.py      # Input builders wrapping operations as PythonJobs
├── serialization.py   # Serializers bridging Euphonic objects <-> custom Data nodes
├── conversions.py     # Maps domain objects to native AiiDA types (StructureData, BandsData, XyData)
├── data/              # Custom AiiDA Data nodes (store JSON in node repository)
└── workflows/         # WorkChains composing PythonJobs and calcfunctions
```

### Critical Invariants:
1. **`operations.py` is strictly AiiDA-free**:
   * Its import chain must never import `aiida` (the package `__init__.py` is empty).
   * This ensures `aiida-pythonjob` can cloudpickle functions *by reference* into lean remote execution environments (`euphonic`, `abinslib`, `resins`, `numpy`, `seekpath` without `aiida-core`).
2. **`PythonJob` return values**:
   * Functions executed inside a `PythonJob` must return plain Python types (`dict`, dataclasses, numbers, lists), **never an AiiDA ORM node**.
   * AiiDA ORM nodes are instantiated parent-side by serializers, custom Data node classes, or `calcfunction`s.
3. **Public API only**:
   * Use only public APIs and official entry points of underlying libraries (`euphonic`, `abinslib`, `resins`, `seekpath`, `aiida`). Never import or invoke private helpers (e.g. `_bands_from_force_constants`).
4. **No `print` in library code**:
   * Emit standard logging using `logging.getLogger(__name__)`. Never configure handlers or log levels in library code (leave that to the host application / AiiDA).
5. **Dependency bounds**:
   * Bound dependencies in `pyproject.toml` according to this package's own direct usage. Avoid overly tight upper bounds that cause resolver conflicts with sibling plugins.

---

## 3. Tooling & Verification

* **Environment & Package Management**: Use `uv` for managing virtual environments and dependencies.
  ```bash
  uv sync
  ```
* **Running Tests**:
  ```bash
  uv run pytest
  ```
  Tests run against an isolated SQLite test profile using `aiida.tools.pytest_fixtures`.
* **Linting & Formatting**:
  ```bash
  uv run ruff check
  uv run ruff format --check
  ```
* **Building Documentation**:
  ```bash
  uv run --group doc make -C docs html
  ```

---

## 4. OpenSpec Workflow

This project uses [OpenSpec](https://openspec.dev/) for spec-driven development:
* **Specs (`openspec/specs/`)**: Define normative behavioral requirements (`SHALL`/`MUST`) and verifiable scenarios (`WHEN`/`THEN`).
* **Changes (`openspec/changes/`)**: Every non-trivial modification, refactor, or feature addition is planned and tracked through structured change proposals (`proposal.md`, `specs/`, `design.md`, `tasks.md`).
* **Main Specs vs. Delta Specs**: Keep main specs in sync when completing changes by archiving or running spec syncs.
