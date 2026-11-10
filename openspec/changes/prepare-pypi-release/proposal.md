# Proposal

## Why

The package has never been released, and downstream users currently install it
from a git URL. A first release on PyPI needs three things the repository does
not have: a release workflow, a distribution name the project is willing to keep,
and a version that is recorded in AiiDA's provenance. The last point matters for a
plugin whose purpose is provenance. AiiDA records a plugin's version on every
process only if the plugin's top-level module defines `__version__`, which this
package does not.

The name decision is also due now. The project will be renamed `aiida-alc-ins`
(import package `aiida_alc_ins`, entry-point prefix `alc_ins`), but the first
release has to keep the current import package and entry-point names so that the
existing downstream code that imports `aiida_pythonjob_ins` keeps working. The
PyPI name is the one name that should not change between releases, so it is chosen
now.

None of this exists yet; this change adds it.

## What Changes

- Name the PyPI distribution `aiida-alc-ins`. The import package stays
  `aiida_pythonjob_ins` and the entry-point prefix stays `pythonjob_ins` for the
  first release. Their rename to `aiida_alc_ins` and `alc_ins` is a separate,
  breaking 0.2 change.
- Add `__version__` to `aiida_pythonjob_ins`, derived from the installed
  distribution's metadata, so `pyproject.toml` stays the single place where the
  version is written.
- Add a release workflow that builds the source and wheel distributions, tests the
  wheel, and publishes to PyPI through trusted publishing. It runs when a GitHub
  release is published, and on manual dispatch of a chosen ref, so that release
  candidates and post-release builds do not need a release page.
- Ignore GitHub releases whose tag does not start with `v`, so that releases made
  for other purposes, such as holding reference data, never start an upload to
  PyPI. The GitHub release itself is unaffected.
- Before anything is uploaded, verify that the version being released matches the
  version in `pyproject.toml`, that it is not a development version, and that the
  test suite passes against the built wheel installed into a clean environment.
- Add two tests that belong in the ordinary suite, not only in releases: every
  entry point the distribution declares loads, and `__version__` equals the version
  declared in `pyproject.toml`.
- Fill in the missing PyPI metadata (project URLs, authors, classifiers,
  keywords).
- Update the places that carry the distribution name: the documentation build,
  the README install instructions, `AGENTS.md`, the OpenSpec project context and
  the changelog links.
- Document the routine release procedure for maintainers, including the version
  number convention (the release commit carries the release version, and `main`
  carries the next development version, such as `0.2.0.dev0`, between releases)
  and how to correct a bad release. The one-off PyPI and GitHub setup is not part
  of that document.

### Assumption

The package has no end users yet, and nodes created by the unreleased code need
not stay loadable. The 0.2 rename of entry points therefore needs no compatibility
aliases or migration, and this change adds none.

## Capabilities

### New Capabilities

- `release-publishing`: how a release reaches PyPI: the triggers, the checks that
  gate the upload, and the separation between building and uploading.

### Modified Capabilities

- `plugin-packaging`: the distribution is named `aiida-alc-ins` while the import
  package keeps its current name, and the package reports its version from its
  distribution metadata so that AiiDA records it in provenance.

## Non-goals

- Renaming the import package or the entry points. That is the 0.2 change.
- Compatibility aliases for old entry-point names or a shim package under the old
  import name.
- Registering the plugin with the AiiDA plugin registry. That waits for 0.2, when
  the names are unified.
- Deriving the version from git tags, or changing the build backend.
- Publishing to TestPyPI. The package is pure Python, its build is simple, and the
  checks above run before any upload. A bad release is corrected by yanking it and
  publishing a post-release or a new version.
- Running the containerized tests, or a Python-version matrix, in the release
  workflow. Both stay in the existing CI. The release workflow runs the remaining
  tests once, on the oldest supported Python.
- Publishing versioned documentation.

## Impact

- `pyproject.toml`: distribution name, PyPI metadata, build-backend module name,
  and a `required-version` for uv that the workflows read, so they no longer pin
  uv individually; the header comment.
- `src/aiida_pythonjob_ins/__init__.py`: `__version__`.
- `.github/workflows/`: a new release workflow; the existing workflows drop their
  uv version pins.
- `tests/`: a version test module and a metadata-driven entry-point test.
- `uv.lock`: the project's own entry follows the new name.
- `docs/source/conf.py`, `docs/source/index.rst`, `README.md`, `AGENTS.md`,
  `openspec/config.yaml`, `CHANGELOG.md`: names, install instructions, links.
- A root-level `RELEASING.md` for maintainers.
- External, outside the repository: a pending trusted publisher on PyPI and a
  matching `pypi` environment in the GitHub repository settings.
- Dependencies: none new, in the runtime dependencies or the `dev` group. The
  metadata check runs `twine`, and the development-version check runs `packaging`,
  both ephemerally through `uv`.
