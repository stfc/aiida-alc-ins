# Tasks

The verification commands below assume a clean build:

```bash
rm -rf docs/source/auto_examples docs/source/autoapi docs/build
uv run --group doc make -C docs html SPHINXOPTS="-W --keep-going"
```

Removing `docs/source/auto_examples` matters because it is a gitignored cache: Sphinx-Gallery skips any example whose checksum matches it. The build needs the system `dot` (graphviz).

## 1. Render WorkChain docstrings

- [x] 1.1 Create `docs/source/_ext/workchain_docs.py` with `RenderedWorkchainDirective(AiidaWorkchainDirective)` and its `setup()`, per design Decisions 1–3:
  - `setup()` calls `app.setup_extension("aiida.sphinxext")`, re-registers `py:aiida-workchain` with `override=True`, and returns `parallel_read_safe: True`.
  - `build_content()` replaces the first child, the raw docstring paragraph, with the docstring cleaned by `inspect.getdoc`, converted by napoleon's `GoogleDocstring`, and parsed with `nested_parse` inside `switch_source_input`.
  - `build_signature()` adds the fully qualified class name to the signature's `ids` and registers it with the Python domain's `note_object`.

  In `docs/source/conf.py`, add `_ext` to `sys.path`, replace `"aiida.sphinxext"` with `"workchain_docs"` in `extensions`, and set `napoleon_custom_sections = ["Exit Codes"]`. Verify that the clean build succeeds, and that `docs/build/html/workflows.html` has:
  - an anchor `id` for each of the 5 documented WorkChains;
  - an "Exit Codes" rubric followed by a bulleted list in each of the 5 descriptions;
  - `ForceConstantsWorkChain` references in other descriptions rendered as links to its anchor.
- [x] 1.2 Verify that no workflow description shows reStructuredText source. Outline blocks are excluded, because they remain preformatted (design Non-Goals). Run:

  ```bash
  uv run python -c "import re, pathlib; h = pathlib.Path('docs/build/html/workflows.html').read_text(); h = re.sub(r'<pre>.*?</pre>', '', h, flags=re.S); t = re.sub(r'<[^>]+>', '', h); bad = [m for m in (':class:', ':func:', ':mod:', '\`\`') if m in t]; assert not bad, bad"
  ```

  It must exit 0.
- [x] 1.3 In `docs/source/workflows.rst`, update the sentence saying exit codes are "documented in the class reference": they now appear on this page, as part of each workflow's description. Add a `CHANGELOG.md` entry under `Unreleased` (Changed) noting that workflow pages now render their descriptions, including exit-code lists and links between workflows. Verify that the clean build still succeeds and the sentence reads correctly on the rendered page.

## 2. Enforce warning-free docs builds in CI

- [x] 2.1 In `.github/workflows/build-docs.yml`, change the build step to `uv run --group doc make -C docs html SPHINXOPTS="-W --keep-going"` (design Decision 4). Verify that this exact command, run locally after removing the gitignored outputs as above, succeeds and reports that all 5 examples ran.

## 3. Integration

- [x] 3.1 Run `uv run ruff check`, `uv run ruff format --check` and `uv run pytest -m "not containerized"`; all pass. `docs/source/_ext/workchain_docs.py` must be covered by ruff.

## Workflow follow-up

- Optionally, open an issue or PR against aiida-core proposing that `AiidaProcessDirective` parse docstrings and register targets. If it is released, the local subclass can be removed.
- Archive the change once implementation and review are complete.
