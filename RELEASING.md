# Releasing

This document is for maintainers. The distribution is `aiida-alc-ins` on PyPI,
and its import package is `aiida_alc_ins`.

The release workflow is `.github/workflows/publish.yml`. It builds the source
distribution and the wheel, checks them, tests the wheel in a clean Python 3.11
environment, and uploads both to PyPI. It does not build from a maintainer's
machine.

## Version convention

- The release commit carries the release version, for example `0.2.0rc1` or
  `0.2.0`.
- Between releases, `main` carries the next intended version with a `.dev0`
  suffix, for example `0.2.0.dev0`.
- The workflow refuses to upload a development version, so `main` cannot reach
  PyPI by accident.

Set the version with `uv version`, not by editing `pyproject.toml`. It updates
`pyproject.toml` and `uv.lock` together:

```bash
uv version 0.2.0rc1
```

## Release steps

1. Set the release version with `uv version <version>`.
2. In `CHANGELOG.md`, move the `[Unreleased]` entries under a new
   `[<version>]` heading, and add a compare link for that heading. Leave an
   empty `[Unreleased]` heading above it.
3. Commit the version and changelog changes, and merge them to `main`.
4. Publish a GitHub release. Create a tag named `v<version>` on the release
   commit, for example `v0.2.0rc1`. The tag must match the version exactly. A
   mismatch fails the run before anything is uploaded.
5. If the `pypi` environment has required reviewers, approve the run in the
   Actions tab.
6. Check the release on PyPI, and install it in a clean environment.
7. Set `main` to the next development version, for example
   `uv version 0.2.0.dev0`, and commit it.

## Tag format

A GitHub release is uploaded to PyPI only if its tag begins with `v`. A release
with any other tag, such as `reference-data-2026`, still exists on GitHub. Its
publish run is skipped, not failed, and nothing is uploaded. Tag package
releases `v<version>`.

## Dispatching a release candidate or another ref

To upload a build without a GitHub release, for example a release candidate:

1. In the Actions tab, open the **Publish** workflow and choose **Run workflow**.
2. The form has two inputs. **Use workflow from** is the branch whose
   `publish.yml` runs. **ref** is what is built and uploaded, at the version
   `pyproject.toml` declares there. Set both to the same branch or tag.
3. Development versions are refused.

PyPI hides pre-releases such as `0.2.0rc1` from default installs, so a release
candidate is installed only with an explicit version.

## Correcting a bad release

PyPI does not allow a version to be uploaded twice, so a bad version is fixed by
a new one.

1. Yank the bad version on PyPI (project page, Manage, then the release, then
   Yank). A yanked version can still be installed by an exact pin, but resolvers
   skip it by default.
2. Publish a corrected version. Use a post-release, such as `0.1.0.post1`, for a
   packaging-only fix, or a new patch version, such as `0.1.1`, for a code fix.
