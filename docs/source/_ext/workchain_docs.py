"""Sphinx extension that renders WorkChain docstrings as reStructuredText.

aiida-core's ``aiida-workchain`` directive inserts the docstring as a raw text
paragraph (``nodes.paragraph(text=process.__doc__)``), so cross-references and
list markup show up literally. This local subclass overrides ``build_content``
to parse the docstring through napoleon and Sphinx's own reST parser, and
``build_signature`` to register each workflow as a link target.
"""

from __future__ import annotations

import inspect

from aiida.sphinxext.workchain import AiidaWorkchainDirective
from docutils import nodes
from docutils.statemachine import StringList
from sphinx.ext.napoleon.docstring import GoogleDocstring
from sphinx.util.docutils import switch_source_input


class RenderedWorkchainDirective(AiidaWorkchainDirective):
    """``aiida-workchain`` directive that renders the docstring as reST.

    The docstring is cleaned with :func:`inspect.getdoc`, converted by napoleon's
    :class:`GoogleDocstring` (so "Exit Codes" custom sections become rubrics),
    and parsed with :meth:`~docutils.parsers.rst.RSTDirectives.state.nested_parse`
    so Sphinx roles and inline literals resolve.
    """

    def build_content(self):
        """Replace the raw docstring paragraph with parsed reST nodes."""
        content = super().build_content()

        doc = inspect.getdoc(self.process)
        if doc is None:
            return content

        converted = GoogleDocstring(
            doc, self.env.config, self.env.app, what="class"
        ).lines()

        # super().build_content() inserts the raw docstring as its first child.
        # Replace it with nodes parsed from the cleaned, napoleon-converted reST.
        content.children[0] = self._parse_docstring("\n".join(converted))
        return content

    def build_signature(self):
        """Register the fully qualified class name as a link target."""
        signature = super().build_signature()
        signature["ids"].append(self.process_name)
        self.env.get_domain("py").note_object(
            self.process_name, "class", self.process_name, location=signature
        )
        return signature

    def _parse_docstring(self, docstring: str) -> nodes.Element:
        """Parse a docstring as reST, returning the resulting node."""
        node = nodes.section()
        node.document = self.state.document
        content = StringList(docstring.splitlines())
        with switch_source_input(self.state, content):
            self.state.nested_parse(content, 0, node)
        return node


def setup(app):
    """Re-register the workchain directive with the rendered subclass."""
    app.setup_extension("aiida.sphinxext")
    app.add_directive_to_domain(
        "py", "aiida-workchain", RenderedWorkchainDirective, override=True
    )
    return {"parallel_read_safe": True}
