# Design: Render WorkChain docstrings as reStructuredText on workflow pages

## Context

`docs/source/workflows.rst` documents each workflow with aiida-core's `aiida-workchain` directive (`aiida.sphinxext`), which builds the page from the live process spec. Three parts of that directive, `aiida/sphinxext/process.py`, matter here. Their structure is the same in aiida-core 2.6.0, the 2.8.1 installed here, and `main`:

- `build_content()` inserts the docstring as `nodes.paragraph(text=self.process.__doc__)`, so it is never parsed.
- `build_signature()` creates a `desc_signature` with no `ids`, and nothing is registered in the Python domain. As a result, `` :class:`...WorkChain` `` references have no target, and WorkChain classes are deliberately excluded from autoapi.
- `build_outline_doctree()` puts the outline, including step-method docstrings, into a `literal_block`.

A throwaway prototype on a copy of the docs confirmed the approach below. The build succeeded with `-W`; every description rendered; "Exit Codes" became a rubric followed by a list; and references to `ForceConstantsWorkChain`, `DispersionWorkChain` and `DosWorkChain` resolved to anchors on the page.

## Goals / Non-Goals

**Goals:** satisfy the spec scenario "Workflow descriptions are rendered, not shown as source", and keep the build free of warnings.

**Non-Goals** (in addition to proposal.md):
- **The Outline block.** It stays the directive's preformatted `literal_block`, so markup in step-method docstrings still shows as written. It reads as a structural listing, and rendering it would mean re-implementing the outline formatter.
- **Upstream changes as a dependency.** Proposing the fix to aiida-core is optional follow-up; the local fix works without it.

## Decisions

### 1. A local subclass of the directive, registered under the same name

Add `docs/source/_ext/workchain_docs.py`. It defines `RenderedWorkchainDirective(AiidaWorkchainDirective)` and its `setup()`:
- calls `app.setup_extension("aiida.sphinxext")`;
- re-registers `py:aiida-workchain` with `override=True` (Sphinx's [`add_directive_to_domain`](https://www.sphinx-doc.org/en/master/extdev/appapi.html#sphinx.application.Sphinx.add_directive_to_domain));
- returns `parallel_read_safe: True`.

`conf.py` adds `_ext` to `sys.path` and lists `workchain_docs` in place of `aiida.sphinxext`. `workflows.rst` does not change.

*Rejected: plainer docstrings.* The descriptions would lose cross-references and formatted lists. The spec asks for markup to be interpreted, not for less of it.

*Rejected: monkeypatching `AiidaProcessDirective` in `conf.py`.* It is hidden global mutation of an installed package; a named subclass is visible and confined to these docs.

*Rejected: documenting WorkChains through autodoc or autoapi instead.* They are excluded on purpose, because static analysis shows step methods rather than the runtime interface. The existing documentation requirement forbids bringing them back.

### 2. Parse the docstring with napoleon and Sphinx's own parser

`build_content()` calls `super().build_content()`, then replaces its first child, the raw docstring paragraph, with parsed nodes:

1. Clean the docstring with `inspect.getdoc(self.process)`.
2. Convert it with `sphinx.ext.napoleon.docstring.GoogleDocstring(doc, self.env.config, self.env.app, what="class").lines()`.
3. Parse the result with `self.state.nested_parse(...)`, inside `switch_source_input` so warnings point at the class.

`conf.py` sets `napoleon_custom_sections = ["Exit Codes"]`, so the existing "Exit Codes:" blocks become a generic section: a rubric followed by the bullet list. No docstring text has to change.

- napoleon is already enabled with Google style (`napoleon_google_docstring = True`). Custom sections are documented in [napoleon's configuration](https://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html#confval-napoleon_custom_sections).
- `nested_parse` resolves roles with Sphinx's own machinery, not plain docutils, so `:class:` and `:func:` work.

*Rejected: `params_style` for "Exit Codes".* It expects `name (type): description` items and would mangle the existing `* 400 (LABEL): message` bullets.

### 3. Register each workflow as a link target

`build_signature()` calls `super()`, adds the fully qualified class name to the signature's `ids`, and calls `self.env.get_domain("py").note_object(fullname, "class", fullname, location=sig)`.

This lets `` :class:`~aiida_pythonjob_ins.workflows.force_constants.ForceConstantsWorkChain` `` in one docstring link to that workflow's entry on the page, which satisfies the scenario's "linking to their target wherever that target is documented". Each class is documented once, so no duplicate-object warnings arise.

### 4. Make CI's docs build treat warnings as errors

`.github/workflows/build-docs.yml` passes `SPHINXOPTS="-W --keep-going"` to `make -C docs html`.

The existing requirement "The documentation build is clean and automated" already says warnings are defects, but CI doesn't enforce it today. The subclass relies on aiida-core internals (Context), so a parsing warning or a change upstream must fail CI rather than quietly degrade the page.

## Risks / Trade-offs

- [The subclass depends on internals of aiida-core's directive: `build_content()`'s first child is the docstring, and `build_signature()` returns the signature node.] → Both are the same from aiida-core 2.6.0 to `main`, which covers the `aiida-core>=2.6,<3` pin. The `-W` build in CI (Decision 4) fails loudly if they change.
- [Docstrings now render as real markup, so malformed reStructuredText in a WorkChain docstring becomes a build warning.] → This is intended. Fix the docstring.
- [Step-method docstrings in the Outline block still show markup as written.] → Accepted (Non-Goals). A later change could override `build_outline_doctree()` if it matters.
- [`napoleon_custom_sections` applies project-wide.] → Only WorkChain docstrings use "Exit Codes", and autoapi excludes those classes, so nothing else changes.
