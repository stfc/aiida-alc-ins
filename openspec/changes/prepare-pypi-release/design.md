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
- A trial `uv build` of this repository already produces a working sdist and wheel
  containing `aiida_pythonjob_ins` and `entry_points.txt`.
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
- Making the release workflow a second test run. It checks the built files, not
  the science.

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
      ref:    {description: Git ref to build, required: true}
      target: {description: Index, type: choice, options: [testpypi, pypi]}
```

- A published release builds `github.event.release.tag_name` and publishes to
  PyPI.
- A dispatch builds `inputs.ref` and publishes to the chosen index. This covers
  release candidates and post-release builds without a release page, and the
  TestPyPI rehearsal.
- Nothing else triggers a publish. The workflow does not run on `push` or
  `pull_request`.

Alternatives considered:

- **Push of a `v*` tag.** Easy to trigger by accident, and failed attempts leave a
  tag that must be deleted and re-pushed.
- **Manual dispatch only** (as in `abinslib`). It works, but the workflow file
  comes from the dispatched branch while the code comes from the named ref, and it
  loses the review point that publishing a release provides.
- **Create the release late in a chain of jobs**, as a compiled-wheel project
  might to avoid a failed public release. Here the package is pure Python and the
  build job runs and verifies before any upload, so a bad release can be deleted
  without anything having reached the index.

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

### 5. Build, verify, then publish, in separate jobs

```
        ┌───────────────────────────────┐
        │ build        (contents: read) │
        │  checkout ref                 │
        │  check tag == version         │
        │  uv build  (sdist + wheel)    │
        │  twine check                  │
        │  smoke test the wheel         │
        │  upload-artifact  dist/       │
        └──────────────┬────────────────┘
                       │ needs
        ┌──────────────▼────────────────┐
        │ publish-testpypi / publish-pypi│
        │   id-token: write             │
        │   environment: testpypi|pypi  │
        │   download-artifact → publish │
        └───────────────────────────────┘
```

- The publishing jobs hold `id-token: write` and do no building. They upload the
  artifact the build job verified, using `pypa/gh-action-pypi-publish`, the action
  PyPI's trusted-publishing documentation uses. For TestPyPI the action's
  repository URL is set to the test index.
- There are two publish jobs, each with its own `if` and fixed `environment`,
  rather than one job with a computed environment name. The environment name is
  part of what the trusted publisher on the index checks, so keeping each one
  literal in the file makes the match easy to read.
- `abinslib` builds and publishes in one job. Splitting them is cheap, and it keeps
  the build tooling and project code from running with a token that can publish.

#### The smoke test

A small script in the repository, run by the build job, installs the built wheel
into a fresh virtual environment on the oldest supported Python and checks that:

1. every entry point in the `aiida.data` and `aiida.workflows` groups that
   belongs to the distribution loads;
2. `aiida_pythonjob_ins.__version__` equals the declared version.

It uses `importlib.metadata` rather than AiiDA's plugin factories, so it needs no
AiiDA profile. Importing the package does read AiiDA's configuration, so the
script points `AIIDA_PATH` at a temporary directory first, as the test suite and
the documentation build already do.

Alternatives considered:

- **Run the existing test suite against the wheel.** It exercises more, but needs
  the test dependencies and the suite's fixtures, and duplicates the CI run.
  Rejected.
- **Skip verification, as `abinslib` does.** A wheel with a missing module or a
  broken entry point is the most likely release error here (see Risks), and
  PyPI cannot replace a published file.

### 6. PyPI metadata

Add to `[project]`:

- `authors`, as in the documentation configuration (the Science and Technology
  Facilities Council).
- `[project.urls]`: the repository `https://github.com/stfc/aiida-alc-ins`, its
  issue tracker and the documentation site.
- `classifiers`: `Development Status :: 3 - Alpha`, `Framework :: AiiDA`,
  the supported Python versions, `Topic :: Scientific/Engineering :: Physics`.
- `keywords`.

No `License ::` classifier is added: the project uses the SPDX `license`
expression and `license-files`, and licence classifiers are deprecated alongside
that form (PEP 639).

### 7. Maintainer documentation lives in `RELEASING.md`

A root-level `RELEASING.md`, not a page of the user documentation, covering the
one-off setup, the release steps and the version convention. User documentation
does not link to specs or to maintainer procedure.

One-off setup, described there:

1. On PyPI, add a pending trusted publisher under the account's "Publishing"
   page: project `aiida-alc-ins`, owner `stfc`, repository `aiida-alc-ins`,
   workflow file name `publish.yml`, environment `pypi`. A pending publisher
   creates the project the first time it is used
   (<https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/>).
2. Repeat on TestPyPI, which is a separate service and account, with environment
   `testpypi`.
3. Create the `pypi` and `testpypi` environments in the GitHub repository. Adding
   required reviewers to `pypi` makes publication need an approval.

## Risks / Trade-offs

- **A wheel with no package code** (the build backend does not find the module
  after the rename) → `module-name` in Decision 1, a spec scenario, and the smoke
  test.
- **A pending publisher does not reserve the name until it is used**; if someone
  registers `aiida-alc-ins` first, the pending publisher is invalidated → set it up
  immediately before the first publish, and rehearse on TestPyPI, which does not
  contend for the production name.
- **The publisher settings must match the workflow exactly** (repository,
  file name, environment) or the first publish fails with an authentication
  error → `RELEASING.md` lists each field, and a TestPyPI rehearsal exercises the
  same file before the first real release.
- **A version cannot be re-uploaded to PyPI.** A bad release is yanked and
  replaced by a new version → verification and the version check run before any
  upload; the rehearsal uses a release candidate.
- **The smoke test installs dependencies from the network**, so it can fail for
  reasons unrelated to the wheel → accepted; a failure blocks a release, not a
  merge.
- **`__version__` falls back to `0+unknown` outside an installed environment**,
  which would record a meaningless plugin version → the scenario covers installed
  environments, and the fallback is preferable to failing at import.
- **One release has differing PyPI and import names**, which can confuse a new
  user → stated in the README beside the install command and in the 0.1
  changelog; removed by the 0.2 rename.
- **The dev-version convention needs a second commit per release and can be
  forgotten** → it is a step in `RELEASING.md`, and a forgotten step only means
  `main` reports the release version a little longer.

## Migration Plan

1. Make the in-repository changes and merge them.
2. Configure the pending publishers and GitHub environments (Decision 7).
3. Rehearse: dispatch the workflow with `target: testpypi` on a release-candidate
   version, install from TestPyPI in a clean environment, and check
   `__version__` and the entry points.
4. Set the release version, publish a GitHub release whose tag matches it, and
   approve the `pypi` environment if reviewers are configured.
5. Set `main` to the next development version, `0.2.0.dev0`.
6. Later, in the 0.2 change: rename the import package and entry points, remove
   `module-name`, and register the plugin with the AiiDA plugin registry.

Rollback: before an upload nothing needs undoing; delete the release and its tag.
After an upload, yank the version on PyPI and release a corrected one.

## Open Questions

- The URL for the documentation project link depends on where the site is hosted
  once the repository moves, and can be filled in without changing anything else.
- Whether the `pypi` environment requires a reviewer is a repository setting. It
  does not affect the workflow file.
