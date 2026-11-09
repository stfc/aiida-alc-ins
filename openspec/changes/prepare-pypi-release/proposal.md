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
- Add a release workflow that builds the source and wheel distributions, verifies
  them, and publishes to PyPI through trusted publishing. It runs when a GitHub
  release is published, and on manual dispatch with a choice of PyPI or TestPyPI,
  so that release candidates and rehearsals do not need a release page.
- Verify, before anything is uploaded, that the version being released matches the
  version in `pyproject.toml`, and that the built wheel installs cleanly and
  exposes every declared entry point.
- Fill in the missing PyPI metadata (project URLs, authors, classifiers,
  keywords).
- Update the places that carry the distribution name: the documentation build,
  the README install instructions, `AGENTS.md`, the OpenSpec project context and
  the changelog links.
- Document the release procedure for maintainers, including the one-off PyPI
  setup and the version number convention: the release commit carries the release
  version, and `main` carries the next development version (such as `0.2.0.dev0`)
  between releases.

### Assumption

The package has no end users yet, and nodes created by the unreleased code need
not stay loadable. The 0.2 rename of entry points therefore needs no compatibility
aliases or migration, and this change adds none.

## Capabilities

### New Capabilities

- `release-publishing`: how a release reaches PyPI: the triggers, the checks that
  gate publication, and the separation between building and publishing.

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
- Running the full test suite, or compiled-wheel tests, in the release workflow.
  The suite runs in the existing CI; the release workflow checks only the built
  distributions.
- Publishing versioned documentation.

## Impact

- `pyproject.toml`: distribution name, PyPI metadata, build-backend module name,
  version handling; the header comment.
- `src/aiida_pythonjob_ins/__init__.py`: `__version__`.
- `.github/workflows/`: a new release workflow.
- `uv.lock`: the project's own entry follows the new name.
- `docs/source/conf.py`, `docs/source/index.rst`, `README.md`, `AGENTS.md`,
  `openspec/config.yaml`, `CHANGELOG.md`: names, install instructions, links.
- Contributor documentation: the release procedure.
- External, outside the repository: a pending trusted publisher on PyPI and on
  TestPyPI, and matching `pypi` and `testpypi` environments in the GitHub
  repository settings.
- Dependencies: none new.
