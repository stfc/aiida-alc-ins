"""Configuration file for the Sphinx documentation builder.

Stack (modelled on abinslib): sphinx-autoapi for API docs from ``src/``,
sphinx-gallery for runnable tutorials (executed at build time, downloadable as
notebooks), myst-parser, napoleon, furo theme.
https://www.sphinx-doc.org/en/master/usage/configuration.html
"""

import importlib.metadata
import os
import sys
import tempfile
from pathlib import Path

# The ``aiida-workchain`` directive imports the workflow classes and calls
# ``load_profile()``, so the build needs an AiiDA profile. Point AIIDA_PATH at a
# throwaway dir and load an in-memory profile (never touches a real ``~/.aiida``).
os.environ.setdefault("AIIDA_PATH", tempfile.mkdtemp(prefix="aiida-docs-config-"))
from aiida import load_profile
from aiida.manage.configuration import get_config
from aiida.storage.sqlite_temp import SqliteTempBackend

get_config(create=True)
load_profile(SqliteTempBackend.create_profile("docs"), allow_switch=True)

# Local Sphinx extensions live in ``_ext``.
sys.path.insert(0, str(Path(__file__).resolve().parent / "_ext"))

project = "aiida-pythonjob-ins"
copyright = "2026, STFC"  # noqa: A001
author = "Science and Technology Facilities Council"
release = importlib.metadata.version("aiida-pythonjob-ins")

# -- General configuration ---------------------------------------------------
extensions = [
    "autoapi.extension",
    "sphinx_gallery.gen_gallery",
    "myst_parser",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "workchain_docs",  # rendered `.. aiida-workchain::` directive (local subclass)
]

templates_path = ["_templates"]
exclude_patterns = ["tutorials/GALLERY_HEADER.rst"]

# -- HTML output (furo, abinslib palette) ------------------------------------
_PALE = "#dae9e0"
_DESATURATED = "#97b1ab"
_BRIGHT = "#c4fcf0"
_LIGHT_GREEN = "#4eae9e"
_GREEN = "#00796b"
_TURQUOISE = "#007e8c"
_DARK_GREEN = "#344b47"
_DARKEST = "#00392f"

html_theme = "furo"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_theme_options = {
    "light_css_variables": {
        "color-brand-primary": _GREEN,
        "color-brand-content": _GREEN,
        "color-brand-visited": _DESATURATED,
        "color-link": _GREEN,
        "color-link--visited": _TURQUOISE,
        "color-link--hover": _DESATURATED,
        "color-admonition-title--note": _LIGHT_GREEN,
        "color-admonition-title-background--note": _BRIGHT,
        "color-api-keyword": _DARK_GREEN,
        "color-api-pre-name": _GREEN,
        "color-api-name": _DARK_GREEN,
        # Referenced from _static/custom.css for the download-button gradient.
        "color-download-button-bg": _PALE,
        "color-download-gradient-top": _PALE,
        "color-download-gradient-bottom": _LIGHT_GREEN,
    },
    "dark_css_variables": {
        "color-brand-primary": _LIGHT_GREEN,
        "color-brand-content": _LIGHT_GREEN,
        "color-brand-visited": _TURQUOISE,
        "color-link": _LIGHT_GREEN,
        "color-link--visited": _GREEN,
        "color-link--hover": _TURQUOISE,
        "color-admonition-title--note": _LIGHT_GREEN,
        "color-admonition-title-background--note": _DARK_GREEN,
        "color-admonition-background": _DARKEST,
        "color-download-button-bg": _DESATURATED,
        "color-download-gradient-top": _LIGHT_GREEN,
        "color-download-gradient-bottom": _GREEN,
    },
}

# -- AutoAPI -----------------------------------------------------------------
autoapi_type = "python"
autoapi_dirs = ["../../src"]
autoapi_options = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
    "imported-members",
]
autodoc_typehints = "signature"

# -- Sphinx gallery ----------------------------------------------------------
sphinx_gallery_conf = {
    "examples_dirs": "tutorials",
    "gallery_dirs": "auto_examples",
    "filename_pattern": r"/plot_",  # only execute plot_*.py
    "ignore_pattern": r"_aiida_setup\.py",  # shared helper, not a gallery item
    "remove_config_comments": True,
}

# -- Napoleon (Google-style docstrings) --------------------------------------
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_custom_sections = ["Exit Codes"]


def _skip_workchains(app, what, name, obj, skip, options):
    """Hide WorkChain classes from autoapi.

    Their runtime-defined input/output spec is invisible to static analysis, so
    autoapi would only show the outline-step methods (an implementation detail).
    They are documented instead by the ``aiida-workchain`` directive (see
    ``workflows.rst``), which renders the actual inputs/outputs.
    """
    if what == "class" and name.endswith("WorkChain"):
        return True
    return skip


def setup(app):
    """Connect the autoapi skip handler."""
    app.connect("autoapi-skip-member", _skip_workchains)
