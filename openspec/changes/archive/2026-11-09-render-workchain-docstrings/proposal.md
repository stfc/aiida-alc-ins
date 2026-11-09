# Proposal: Render WorkChain docstrings as reStructuredText on workflow pages

## Why

On `workflows.rst`, every WorkChain's docstring is shown as raw text: readers see `` :class:`~aiida_pythonjob_ins...` ``, double backticks and the unformatted "Exit Codes:" list. The cause is upstream. aiida-core's `aiida-workchain` directive (`aiida/sphinxext/process.py`, unchanged on `main` as of aiida-core 2.8.1) inserts the docstring with `nodes.paragraph(text=self.process.__doc__)` instead of parsing it. Port `help` strings are parsed, but with plain docutils, so Sphinx roles in them wouldn't resolve either. These pages are the only place WorkChain docstrings appear, because the API reference deliberately excludes WorkChain classes.

## What Changes

- Workflow pages render each WorkChain's docstring as reStructuredText, with resolved cross-references, inline literals and a formatted exit-code list. The docs build must stay clean with warnings treated as errors.
- Implementation is for design. The candidates are:
  - a small local subclass of the directive that parses the docstring with Sphinx's own parser;
  - an upstream fix to aiida-core, with the local subclass as a stopgap until it is released;
  - plainer docstrings.

## Capabilities

### New Capabilities

*(None)*

### Modified Capabilities

- `documentation`: "Workflow interfaces are documented from their runtime spec" gains a scenario saying that docstring markup on a workflow page is rendered, not shown literally.

## Non-goals

- Changing how input and output ports are listed. That includes the `NoneType` shown in the valid types of optional ports, which is also upstream behaviour.
- Rewriting docstring content beyond what rendering requires.
- Bringing WorkChain classes back into the API reference.

## Impact

- `docs/source/conf.py`, plus a small local Sphinx extension if the subclass route is chosen.
- WorkChain docstrings under `src/aiida_pythonjob_ins/workflows/`, only where they don't parse cleanly.
- Optionally, an issue or PR against aiida-core.
