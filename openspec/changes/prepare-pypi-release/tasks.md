# Tasks

Notes for the implementer:

- Run all commands from `/workspace/aiida_pythonjob_ins`.
- The import package, the entry-point names and the test names stay as they are.
  Only the distribution name changes in this change (design.md, Decision 1).
- `src/aiida_pythonjob_ins/__init__.py` is imported by `operations.py`, whose
  import chain must stay free of AiiDA. `importlib.metadata` is standard library,
  so it is fine, but do not import anything else there.
- Do not add tests that only check that metadata fields are present. The tests
  here check behaviour: the reported version, and what AiiDA records.

## 1. Distribution name, metadata and version

- [ ] 1.1 In `pyproject.toml`, change `name` to `aiida-alc-ins`; add
  `[tool.uv.build-backend]` with `module-name = "aiida_pythonjob_ins"`; add
  `authors`, `keywords`, `classifiers` and `[project.urls]` as in design.md
  Decision 6 (no `License ::` classifier). Update the file's header comment. Run
  `uv lock`. Verify with `uv build --out-dir /tmp/dist-check` that both the sdist
  and the wheel list `aiida_pythonjob_ins/__init__.py` and, for the wheel,
  `entry_points.txt` with all eight entry points (use
  `uv run python -c "import zipfile,glob; print(zipfile.ZipFile(glob.glob('/tmp/dist-check/*.whl')[0]).namelist())"`),
  and that `git diff uv.lock` changes only the project's own entry.
- [ ] 1.2 In `src/aiida_pythonjob_ins/__init__.py`, add `__version__` as in
  design.md Decision 2, with a one-line comment saying it exists because AiiDA
  records the plugin version from it. Add `tests/test_version.py` with two tests:
  `__version__` equals `importlib.metadata.version("aiida-alc-ins")`; and a
  `ForceConstantsWorkChain` run given a prepared `ForceConstantsData` records that
  value as `node.base.attributes.get("version")["plugin"]`. Verify with
  `uv run pytest tests/test_version.py tests/test_import_purity.py`.
- [ ] 1.3 In `docs/source/conf.py`, change `project` and the
  `importlib.metadata.version(...)` argument to `aiida-alc-ins`, and update the
  title in `docs/source/index.rst`. Verify with
  `uv run --group doc make -C docs html SPHINXOPTS="-W --keep-going"`, which must
  finish without warnings.
- [ ] 1.4 Update the remaining places that carry the distribution name: the
  install instructions in `README.md` (`pip install aiida-alc-ins`, with one
  sentence saying that the import package is still `aiida_pythonjob_ins` until
  0.2), `AGENTS.md`, the project context in `openspec/config.yaml`, and the
  `[Unreleased]` link at the bottom of `CHANGELOG.md` (the repository is
  `stfc/aiida-alc-ins`). Verify with
  `grep -rIn "aiida-pythonjob-ins" --exclude-dir=.venv --exclude-dir=build --exclude-dir=archive --exclude-dir=.git --exclude=uv.lock .`,
  which must print nothing except this change's own artifacts.

## 2. Release workflow

- [ ] 2.1 Add `.github/scripts/smoke_test_wheel.py`, implementing the smoke test
  in design.md Decision 5. It takes the expected version as an argument, sets
  `AIIDA_PATH` to a temporary directory before importing the package, loads every
  entry point of the distribution in the `aiida.data` and `aiida.workflows`
  groups, and exits non-zero with a message naming the first failure. Verify
  locally: `uv build`, then `uv venv --python 3.11 /tmp/smoke`, install the wheel
  into it with `uv pip install --python /tmp/smoke/bin/python dist/*.whl`, and run
  the script with the correct version (exit 0) and a wrong version (non-zero).
  Verify the entry-point failure path by editing a copy of the unpacked wheel's
  `entry_points.txt` in `/tmp` to name a missing module, and checking that the
  script reports it. Do not commit the copy.
- [ ] 2.2 Add `.github/workflows/publish.yml`, with the triggers, jobs,
  permissions and environments in design.md Decisions 3, 4 and 5: a
  credential-free `build` job (version check on release events, `uv build`,
  `twine check`, the smoke test, `upload-artifact`) and `publish-testpypi` and
  `publish-pypi` jobs that hold `id-token: write`, name their environments
  literally, and use `pypa/gh-action-pypi-publish`. The file name must be exactly
  `publish.yml`, because the trusted publisher on the index is configured with it.
  Verify that the file parses as YAML, that no step outside the two publish jobs
  has `id-token`, and, if `actionlint` is available, that it passes. Verify the
  version check by running its shell fragment with `TAG=v0.1.0` (passes against
  the current version), `TAG=v0.1.1` and `TAG=0.1.0` (the first fails; state in a
  comment what the third does).
- [ ] 2.3 Check the workflow against each scenario in
  `specs/release-publishing/spec.md`: no `push` or `pull_request` trigger, no
  stored token, production publishing bound to the `pypi` environment, the version
  check before upload, verification before upload, and the publish jobs running no
  build. Verify by reading the file once per scenario and noting any gap.

## 3. Maintainer documentation

- [ ] 3.1 Add `RELEASING.md` at the repository root, covering design.md
  Decision 7 (the three one-off setup steps with their exact field values), the
  release steps (set the version with `uv version`, update `CHANGELOG.md` including
  the compare links, publish the release, approve the environment), the TestPyPI
  rehearsal with a release candidate, the tag format `v<version>`, and the
  post-release step of setting `0.2.0.dev0`-style development versions. Verify
  against the last scenario of the `release-publishing` spec: the document covers
  configuring the trusted publisher, setting the release version, publishing, and
  setting the next development version.
- [ ] 3.2 Add to `[Unreleased]` in `CHANGELOG.md`: the PyPI distribution name, the
  `__version__` attribute, and that the import package and entry points keep their
  current names until 0.2. Verify that the entries describe the net change since
  the last state described in the changelog, as the other entries do.

## 4. Integration checks

- [ ] 4.1 Run `uv run ruff check`, `uv run ruff format --check` and
  `uv run pytest`. Verify that all three pass. If `tests/test_remote_ssh.py` errors
  because no container runtime is available, confirm that the same errors occur
  without this change before ignoring them.
- [ ] 4.2 Run `openspec validate prepare-pypi-release`. Run `git status` and
  confirm that it lists only the files named in this task list and this change
  directory, with no scratch scripts and no files under `/tmp` copied in. Verify
  that validation passes and no unexpected files appear.

## Workflow follow-up

- Outside the repository, before the first release: add the pending trusted
  publisher on PyPI and on TestPyPI, and create the `pypi` and `testpypi`
  environments in the GitHub repository (`RELEASING.md`).
- Rehearse with a release-candidate dispatch to TestPyPI, then publish the release.
- Set `main` to the next development version after the release.
- Archive the change after review. The 0.2 rename, which removes `module-name`
  and registers the plugin with the AiiDA registry, is a separate change.
