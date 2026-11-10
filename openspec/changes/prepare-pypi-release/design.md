# Design

## Context

See proposal.md (Why) for motivation and `specs/` for the required behaviour.

Current state:

- `pyproject.toml` declares `name = "aiida-pythonjob-ins"` and a literal
  `version = "0.1.0"`, built by `uv_build`. It has no `[project.urls]`, `authors`
  or `classifiers`. `uv.lock` carries the project's own entry with the same name
  and version.
- The version is read in one place, `docs/source/conf.py`, as
  `importlib.metadata.version("aiida-pythonjob-ins")`. The package defines no
  `__version__`.
- AiiDA's plugin version provider records `version.plugin` on a process only when
  `__version__` exists on the plugin's top-level module (read from
  `aiida/plugins/utils.py`, `PluginVersionProvider.get_version_info`). Today only
  `version.core` is recorded.
- There are no git tags and no release workflow. The sibling project `abinslib`
  publishes with a single-job `workflow_dispatch` workflow that takes a tag input,
  builds with `python -m build`, and uses trusted publishing with a `pypi`
  environment. It does not check that the tag matches the version.
- A trial `uv build` of this repository already produces a working sdist and a
  single `py3-none-any` wheel containing `aiida_pythonjob_ins` and
  `entry_points.txt`.
- The tests live in `tests/`, outside the wheel, and the project uses a src
  layout, so nothing puts the source tree on `sys.path`. In a fresh environment
  with the wheel installed, running pytest from the checkout imports the installed
  package. A trial run on Python 3.11 (wheel plus the `dev` group, installed with
  `uv pip install <wheel> --group dev`) passed all 117 tests that do not need a
  container runtime, in about 40 seconds.
- `tests/test_entry_points.py` lists the entry points by hand, and there is no
  test of the package version.
- `uv_build` derives the module name from the project name. Renaming the
  distribution without telling it the module name would build a wheel with no code
  in it.

The final names are `aiida-alc-ins`, `aiida_alc_ins` and `alc_ins`. This change
adopts only the first, for the reasons in the proposal.

## Goals / Non-Goals

**Goals:**

- A release is one reviewed action, and a mistake is caught before anything
  reaches the index.
- The version is written once.
- The 0.2 rename needs only a rename, not further packaging work.

**Non-Goals:**

- Anything the proposal lists as a non-goal.
- Making the release workflow a second copy of `ci.yml`. It runs the tests once,
  against the built wheel, and leaves the version matrix and the container tests
  to CI.

## Decisions

### 1. Name the distribution `aiida-alc-ins`; keep the import package

```toml
[project]
name = "aiida-alc-ins"

[tool.uv.build-backend]
module-name = "aiida_pythonjob_ins"
```

`module-name` is the documented `uv_build` setting for a module whose name differs
from the project's
(<https://docs.astral.sh/uv/concepts/build-backend/>). The 0.2 change removes it
along with the rename of `src/aiida_pythonjob_ins`.

Alternatives considered:

- **Publish as `aiida-pythonjob-ins`, rename later.** The PyPI name is the one
  that cannot move without orphaning a project, and a second name would have to be
  maintained or deprecated. Rejected.
- **Do the whole rename now.** It would break the downstream code that imports
  `aiida_pythonjob_ins` from the git repository, which is the reason for the
  staged approach.

The cost is one release in which the PyPI name and the import name differ. The
README says so beside the install command.

### 2. One written version; `__version__` derives from it

`pyproject.toml` stays the only place the version is written. The package exposes
it as:

```python
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("aiida-alc-ins")
except PackageNotFoundError:  # running from a source tree that is not installed
    __version__ = "0+unknown"
```

The argument is the distribution name, which remains `aiida-alc-ins` after the
0.2 rename. The fallback keeps `import aiida_pythonjob_ins` working in an
unusual environment instead of failing at import, and the specs' scenarios are
about installed environments.

`__version__` is provided for AiiDA's benefit, not as a recommended way for users
to read the version. Current guidance for libraries is to leave it out and point
users to `importlib.metadata`, but AiiDA records the plugin version only through
this attribute, and a provenance record cannot be added after the fact.

`docs/source/conf.py` keeps reading the version from `importlib.metadata`, with
the new distribution name. A stale name raises `PackageNotFoundError` and fails
the documentation build, which the existing pull-request build would show.

Alternatives considered:

- **Derive the version from git tags** (`hatch-vcs`, `setuptools-scm`,
  `uv-dynamic-versioning`). This removes tag/version mismatch by construction and
  gives dev versions between releases. It needs a different build backend, since
  `uv_build` supports only a static version, a full-depth checkout in CI, and
  adds a way for a source tarball without git metadata to report a wrong version.
  At a low release cadence the mismatch check in Decision 4 is enough. Rejected for
  now.
- **Write the version in `__init__.py` as well.** Two places to edit. Rejected.

#### Version convention between releases

The release commit carries the release version (`0.1.0`). Immediately afterwards,
`main` is set to the next intended version with a `.dev0` suffix, `0.2.0.dev0`
here because the next release is the breaking rename. PEP 440 orders these as
`0.1.0 < 0.2.0.dev0 < 0.2.0rc1 < 0.2.0`
(<https://peps.python.org/pep-0440/>). `uv version <value>` edits
`pyproject.toml` and updates `uv.lock` together, so the lock cannot be left stale
by a hand edit.

The alternative, leaving the released number on `main` until the next bump, needs
no second commit. It makes every build of `main` report the same version as the
release, which is misleading in bug reports and in the provenance this change
sets out to record. Downstream code that wants stability pins the tag, not a
branch.

### 3. Triggers: a published release, or a manual dispatch

```yaml
on:
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      ref: {description: Git ref to build and publish, required: true}
```

- A published release builds `github.event.release.tag_name`, provided the tag
  starts with `v`. A GitHub release with any other tag, such as one made to hold
  reference data, still exists but starts no upload to PyPI: the workflow's jobs
  are skipped, not failed.
- A dispatch builds `inputs.ref`. This covers release candidates and post-release
  builds without a release page.
- Both publish to PyPI, and both pass through the `pypi` environment, so a
  required reviewer on that environment gates either.
- Nothing else triggers a publish. The workflow does not run on `push` or
  `pull_request`.

The tag-prefix rule is one condition on the `build` job. Throughout this change
"release" means a GitHub release, and "upload" means sending files to PyPI; the
first can happen without the second.

```yaml
if: github.event_name != 'release' || startsWith(github.event.release.tag_name, 'v')
```

| Event | `event_name != 'release'` | `startsWith(tag, 'v')` | `build` runs? |
|---|---|---|---|
| Dispatch | true | (no release tag) | yes |
| Release tagged `v0.1.0` | false | true | yes |
| Release tagged `reference-data-2026` | false | false | no |

The first clause exists because a dispatch has no release tag: without it,
`startsWith` would be false and every dispatch would be skipped. `test-wheel` and
`publish` depend on `build`, so they are skipped with it. A skipped run does not
mark the tagged commit as failed, whereas a failure would, which can put a red
mark beside the latest commit on the repository page when a release is made from
the head of the default branch.

The consequence is a convention: a package release is tagged `v<version>`. A
GitHub release tagged without the `v` is silently not uploaded, not rejected, and
`RELEASING.md` says so. The tag/version check of Decision 4 still applies to every
`v` tag.

Alternatives considered:

- **Push of a `v*` tag.** Easy to trigger by accident, and failed attempts leave a
  tag that must be deleted and re-pushed.
- **Manual dispatch only** (as in `abinslib`). It works, but the workflow file
  comes from the dispatched branch while the code comes from the named ref, and it
  loses the review point that publishing a release provides.
- **A test-index target (TestPyPI) for rehearsals.** It needs a second account, a
  second pending publisher and a second environment. The package is pure Python
  with a simple build, and the tests and checks below run before any upload, so
  the rehearsal buys little. A bad release is yanked and replaced by a
  post-release (`0.2.0.post1`) or a new version. Rejected.
- **Create the release late in a chain of jobs**, as a compiled-wheel project
  might to avoid a failed public release. Here the build and test jobs run before
  any upload, so a bad release can be deleted without anything having reached the
  index.

### 4. The tag must match the declared version

For the release event only, the build job compares the tag with the version at
that tag:

```bash
test "${TAG#v}" = "$(uv version --short)"
```

A tag is therefore `v` followed by the exact version string, such as `v0.2.0rc1`.
No normalisation is attempted, so a tag such as `v0.2.0-rc.1` fails the check and
is corrected. A dispatch has no tag to compare, and publishes the version declared
at its ref. If the index already has that version, it rejects the upload.

For both triggers, the build job also refuses a development version, so that
publishing from `main` between releases (when it carries `0.2.0.dev0`) cannot reach
the index by accident:

```bash
uv run --no-project --with packaging python -c '
import sys
from packaging.version import Version
version = Version(sys.argv[1])
sys.exit(f"{version} is a development release; not publishing") if version.is_devrelease else None
' "$(uv version --short)"
```

`Version.is_devrelease` is the right property. `is_prerelease` is also true for
development versions, and for release candidates and alphas, which are meant to be
publishable. `is_devrelease` is true for `0.2.0.dev0`, for its other spellings
(`0.2.0-dev0` normalises to the same version) and for `0.1.0.post1.dev0`, and false
for `0.2.0rc1`, `0.2.0a1` and `0.1.0.post1`. `packaging` runs ephemerally through
`uv run --with`, so it is not added to the `dev` group.

### 5. Build, test the wheel, then publish, in separate jobs

```
        ┌───────────────────────────────┐
        │ build        (contents: read) │
        │  checkout ref                 │
        │  check tag == version         │
        │  uv build  (sdist + wheel)    │
        │  uvx twine check              │
        │  upload-artifact  dist/       │
        └──────────────┬────────────────┘
                       │ needs
        ┌──────────────▼────────────────┐
        │ test-wheel   (contents: read) │
        │  checkout ref (for tests/)    │
        │  download-artifact            │
        │  uv venv --python 3.11        │
        │  uv pip install wheel --group dev
        │  pytest -m "not containerized"│
        └──────────────┬────────────────┘
                       │ needs
        ┌──────────────▼────────────────┐
        │ publish      (id-token: write)│
        │  environment: pypi            │
        │  download-artifact → publish  │
        └───────────────────────────────┘
```

- The `publish` job holds `id-token: write` and does no building. It uploads the
  artifact the earlier jobs built and tested, using
  `pypa/gh-action-pypi-publish`, the action PyPI's trusted-publishing
  documentation uses. `abinslib` builds and publishes in one job. Splitting them
  is cheap, and it keeps the build tooling and project code from running with a
  token that can publish.
- The `test-wheel` job checks out the same ref only to obtain `tests/` and
  `pyproject.toml`, which are not in the wheel. It installs the wheel, not the
  project, so the source tree is not importable. A short step after the install
  asserts that `aiida_pythonjob_ins.__file__` is under `site-packages`, so a
  path leak cannot produce a false pass.
- There is one wheel for all Python versions, so one environment is enough. It
  uses the oldest supported Python, 3.11, which also checks the lower bound of
  `requires-python`. The version matrix and the containerized tests stay in
  `ci.yml`, which already runs on every change.
- The wheel is installed without the lock file, so its dependencies are resolved
  as a PyPI user would resolve them. That tests what is shipped. Upstream drift
  can therefore fail a release run for reasons unrelated to the change, which is
  the signal a release should give.
- `-m "not containerized"` is enough to exclude the three SSH tests, and nothing
  else needs ignoring.

Tests that are not release-specific live in the ordinary suite, so they also run
on every CI run:

- a test that every entry point the distribution declares in the `aiida.data` and
  `aiida.workflows` groups loads, driven by the installed distribution's metadata
  so that a newly declared entry point cannot be left out of the hand-written
  list in `tests/test_entry_points.py`;
- tests that `__version__` equals both the installed metadata and the version
  declared in `pyproject.toml` (the latter catches a stale editable install), and
  that a process records it as its plugin version.

Alternatives considered:

- **A standalone smoke-test script** that installs the wheel and checks the entry
  points and the version. It covers less than the suite, is a second place that
  encodes what "working" means, and as a Python file under `.github/` it is
  subject to the project's lint rules. Rejected in favour of the tests above.
- **Run the containerized tests too.** It needs the container image build that
  `ci.yml` does, for about five minutes of extra setup, and adds no packaging
  coverage. Rejected.
- **Run the same job in `ci.yml` as well**, to catch a packaging mistake on every
  pull request. It would help, but changes CI for everyone, and is easy to add
  later. Deferred.

### 6. PyPI metadata

Add to `[project]`:

- `authors`: Adam J. Jackson, `adam.jackson@stfc.ac.uk`. The institutional address
  tells a reader which organisation to contact if the individual is unavailable.
- `[project.urls]`: `Homepage` is the repository,
  `https://github.com/stfc/aiida-alc-ins`; `Documentation` is the GitHub Pages
  site, `https://stfc.github.io/aiida-alc-ins/`; `Issues` is the repository's
  issue tracker; `Changelog` is `CHANGELOG.md` on the default branch.
- `classifiers`: `Development Status :: 3 - Alpha`, `Framework :: AiiDA`,
  `Intended Audience :: Science/Research`, `Operating System :: OS Independent`,
  `Programming Language :: Python :: 3` with the versions 3.11 to 3.14, and
  `Topic :: Scientific/Engineering :: Physics`. All of these are in the list of
  valid trove classifiers.
- `keywords`: `aiida`, `phonons`, `lattice dynamics`,
  `inelastic neutron scattering`, `euphonic`, `workflows`.

No `License ::` classifier is added: the project uses the SPDX `license`
expression and `license-files`, and licence classifiers are deprecated alongside
that form (PEP 639).

### 7. Maintainer documentation lives in `RELEASING.md`

A root-level `RELEASING.md`, not a page of the user documentation, covering the
routine release steps, the version convention and how to correct a bad release.
User documentation does not link to specs or to maintainer procedure.

Correcting a bad release: yank the version on PyPI, then publish either a
post-release (`0.2.0.post1`) for a packaging-only fix or a new patch version for a
code fix. A yanked version stays installable by exact pin but is skipped by
resolvers.

It does not describe the initial PyPI and GitHub setup. That is done once by the
maintainers and is recorded here, in the migration plan, for whoever repeats it:

1. On PyPI, add a pending trusted publisher under the account's "Publishing"
   page: project `aiida-alc-ins`, owner `stfc`, repository `aiida-alc-ins`,
   workflow file name `publish.yml`, environment `pypi`. A pending publisher
   creates the project the first time it is used
   (<https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/>).
2. Create the `pypi` environment in the GitHub repository. Adding required
   reviewers to it makes publication need an approval.

## Risks / Trade-offs

- **A wheel with no package code** (the build backend does not find the module
  after the rename) → `module-name` in Decision 1, a spec scenario, and the test
  run, which fails at import.
- **A false pass, with the tests importing the source tree instead of the wheel**
  → the src layout, installing the wheel and not the project, and the
  `site-packages` assertion in Decision 5.
- **A pending publisher does not reserve the name until it is used**; if someone
  registers `aiida-alc-ins` first, the pending publisher is invalidated → set it up
  immediately before the first publish.
- **The publisher settings must match the workflow exactly** (repository, file
  name, environment) or the first publish fails with an authentication error →
  the setup fields are listed in Decision 7. A failed authentication leaves the
  index unchanged, so the cost is a re-run.
- **A version cannot be re-uploaded to PyPI, and there is no rehearsal on a test
  index** → the version check and the wheel test run before any upload; a bad
  release is yanked and replaced (Decision 7). The first publish could be a
  release candidate dispatched from a ref, which PyPI hides from default installs.
- **The wheel test installs dependencies from the network**, unlocked, so it can
  fail for reasons unrelated to the wheel → accepted; a failure blocks a release,
  not a merge.
- **The wheel is tested on one Python version** → the others run in `ci.yml`, and
  the package is pure Python.
- **`__version__` falls back to `0+unknown` outside an installed environment**,
  which would record a meaningless plugin version → the scenarios cover installed
  environments, and the fallback is preferable to failing at import.
- **One release has differing PyPI and import names**, which can confuse a new
  user → stated in the README beside the install command and in the 0.1
  changelog; removed by the 0.2 rename.
- **The dev-version convention needs a second commit per release and can be
  forgotten** → it is a step in `RELEASING.md`, and a forgotten step only means
  `main` reports the release version a little longer.

## Migration Plan

1. Make the in-repository changes and merge them.
2. Configure the pending publisher and the GitHub `pypi` environment (the two
   steps in Decision 7).
3. Set the release version, publish a GitHub release whose tag matches it, and
   approve the `pypi` environment if reviewers are configured.
4. Install `aiida-alc-ins` from PyPI in a clean environment and check
   `__version__` and the entry points.
5. Set `main` to the next development version, `0.2.0.dev0`.
6. Later, in the 0.2 change: rename the import package and entry points, remove
   `module-name`, and register the plugin with the AiiDA plugin registry.

Rollback: before an upload nothing needs undoing; delete the release and its tag.
After an upload, yank the version on PyPI and release a post-release or a new
version.

## Open Questions

- Whether the `pypi` environment requires a reviewer is a repository setting. It
  does not affect the workflow file.
