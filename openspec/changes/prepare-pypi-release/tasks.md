# Tasks

Notes for the implementer:

- Run all commands from `/workspace/aiida_pythonjob_ins`.
- The import package, the entry-point names and the existing test names stay as
  they are. Only the distribution name changes (design.md, Decision 1).
- `src/aiida_pythonjob_ins/__init__.py` is imported by `operations.py`, whose
  import chain must stay free of AiiDA. `importlib.metadata` is standard library,
  so it is fine, but do not import anything else there.
- The new tests check behaviour: the reported version, what AiiDA records, and
  that declared entry points load. Do not add tests that only check that metadata
  fields are present.

## 1. Distribution name, metadata and version

- [x] 1.1 In `pyproject.toml`, change `name` to `aiida-alc-ins`; add
  `[tool.uv.build-backend]` with `module-name = "aiida_pythonjob_ins"`; add
  `authors` (`Adam J. Jackson <adam.jackson@stfc.ac.uk>`), `keywords`,
  `classifiers` and `[project.urls]` with exactly the values in design.md
  Decision 6 (no `License ::` classifier). Update the file's header comment. Run
  `uv lock`. Verify with `uv build --out-dir /tmp/dist-check` that the sdist and the
  wheel list `aiida_pythonjob_ins/__init__.py` and that the wheel's
  `entry_points.txt` lists all eight entry points (for the wheel, use
  `uv run python -c "import zipfile,glob; print(zipfile.ZipFile(glob.glob('/tmp/dist-check/*.whl')[0]).namelist())"`),
  and that `git diff uv.lock` changes only the project's own entry.
- [x] 1.2 In `src/aiida_pythonjob_ins/__init__.py`, add `__version__` as in
  design.md Decision 2, with a one-line comment saying it exists because AiiDA
  records the plugin version from it. Add `tests/test_version.py` with three tests:
  `__version__` equals `importlib.metadata.version("aiida-alc-ins")`;
  `__version__` equals the `project.version` read from `pyproject.toml` with
  `tomllib`; and a `ForceConstantsWorkChain` run given a prepared
  `ForceConstantsData` records the same value as
  `node.base.attributes.get("version")["plugin"]`. Verify with
  `uv run pytest tests/test_version.py tests/test_import_purity.py`.
- [x] 1.3 In `tests/test_entry_points.py`, add a test, driven by
  `importlib.metadata.distribution("aiida-alc-ins").entry_points`, that every entry
  point in the `aiida.data` and `aiida.workflows` groups loads and is a class. Keep
  the existing hand-written tests. Verify with
  `uv run pytest tests/test_entry_points.py -v` that the new test covers all eight
  entry points.
- [x] 1.4 In `docs/source/conf.py`, change `project` and the
  `importlib.metadata.version(...)` argument to `aiida-alc-ins`, and update the
  title in `docs/source/index.rst`. Verify with
  `uv run --group doc make -C docs html SPHINXOPTS="-W --keep-going"`, which must
  finish without warnings.
- [x] 1.5 Update the remaining places that carry the distribution name. In
  `README.md` add a short "Installation" section (it has none for users; the only
  install command is the developer `uv sync`) giving `pip install aiida-alc-ins`
  and one sentence saying that the import package is still `aiida_pythonjob_ins`
  until 0.2. Then update `AGENTS.md`, the project context in `openspec/config.yaml`, and the
  `[Unreleased]` link at the bottom of `CHANGELOG.md` (the repository is
  `stfc/aiida-alc-ins`). Verify with
  `grep -rIn "aiida-pythonjob-ins" --exclude-dir=.venv --exclude-dir=build --exclude-dir=archive --exclude-dir=.git --exclude=uv.lock .`,
  which must print nothing except this change's own artifacts.

## 2. Release workflow

- [x] 2.1 Add `.github/workflows/publish.yml`, with the triggers, jobs,
  permissions and environment in design.md Decisions 3, 4 and 5:
  - `build`: carries the tag-prefix condition from design.md Decision 3 (the
    other jobs depend on it, so they are skipped with it); credential-free; the
    version check on release events; the development-version refusal on both
    triggers (design.md Decision 4); `uv build`; `uvx twine check`;
    `upload-artifact`.
  - `test-wheel`: credential-free; checks out the ref, downloads the artifact,
    creates a Python 3.11 environment with `uv venv`, installs the wheel with
    `uv pip install <wheel> --group dev`, asserts that
    `aiida_pythonjob_ins.__file__` is under `site-packages`, and runs
    `python -m pytest -m "not containerized"` with that environment's interpreter
    (never `uv run`, which would use the project environment).
  - `publish`: `needs` both, holds `id-token: write`, names the `pypi` environment
    literally, and uses `pypa/gh-action-pypi-publish` on the downloaded artifact.

  The file name must be exactly `publish.yml`, because the trusted publisher on
  the index is configured with it. Verify that the file parses as YAML, that only
  the `publish` job has `id-token`, and, if `actionlint` is available, that it
  passes. Verify the test job's commands locally in `/tmp`: `uv build`, a Python
  3.11 environment, the wheel installed with `--group dev`, and
  `python -m pytest -m "not containerized"` passing from the repository root.
  Verify the version check by running its shell fragment with `TAG=v0.1.0`
  (passes against the current version), `TAG=v0.1.1` (fails) and `TAG=0.1.0`
  (state in a comment what it does). Verify the development-version refusal by
  running its fragment with the version argument replaced by `0.2.0.dev0` and
  `0.1.0.post1.dev0` (both refused), and `0.2.0rc1`, `0.1.0.post1` and `0.1.0`
  (all accepted).
- [x] 2.2 Check the workflow against each scenario in
  `specs/release-publishing/spec.md`: no `push` or `pull_request` trigger, no
  stored token, a GitHub release with a non-`v` tag skipped (and left published), publication bound to the
  `pypi` environment, the version check
  before upload, the development-version refusal before upload, the tests running
  against the installed wheel before upload, and the publish job running no
  build. Verify by reading the file once per scenario
  and noting any gap.

## 3. Maintainer documentation

- [x] 3.1 Add `RELEASING.md` at the repository root, covering design.md
  Decision 7: the release steps (set the version with `uv version`, update
  `CHANGELOG.md` including the compare links, publish the release, approve the
  environment if one is required), the tag format `v<version>` and that a release
  tagged any other way still exists on GitHub but is not uploaded to PyPI and is
  skipped without a failure (so a package release tagged without the `v` is not
  uploaded, silently), dispatching a
  release candidate from a ref, the post-release step of setting `0.2.0.dev0`-style
  development versions, and how to correct a bad release (yank, then a post-release
  or a new version). Do not include the initial PyPI and GitHub setup. Verify
  against the last two scenarios of the `release-publishing` spec: the document
  covers setting the release version, publishing and the next development version,
  and withdrawing and replacing a bad release.
- [x] 3.2 Add to `[Unreleased]` in `CHANGELOG.md`: the PyPI distribution name, the
  `__version__` attribute, and that the import package and entry points keep their
  current names until 0.2. Verify that the entries describe the net change since
  the last state described in the changelog, as the other entries do.

## 4. Integration checks

- [x] 4.1 Run `uv run ruff check`, `uv run ruff format --check` and
  `uv run pytest`. Verify that all three pass. If `tests/test_remote_ssh.py` errors
  because no container runtime is available, confirm that the same errors occur
  without this change before ignoring them.
- [x] 4.2 Run `openspec validate prepare-pypi-release`. Run `git status` and
  confirm that it lists only the files named in this task list and this change
  directory, with no scratch scripts and no files from `/tmp` copied in. Verify
  that validation passes and no unexpected files appear.

## Workflow follow-up

- Outside the repository, before the first release: add the pending trusted
  publisher on PyPI and create the `pypi` environment in the GitHub repository
  (design.md, Decision 7). This is deliberately not in `RELEASING.md`.
- Publish the release, then set `main` to the next development version.
- Archive the change after review. The 0.2 rename, which removes `module-name`
  and registers the plugin with the AiiDA registry, is a separate change.
