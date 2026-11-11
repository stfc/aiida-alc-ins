"""AiiDA plugin for inelastic neutron scattering workflows using PythonJob."""

from importlib.metadata import PackageNotFoundError, version

# AiiDA records the plugin version in each process's provenance only from this
# attribute, so it is kept even though users should read the version through
# importlib.metadata. The value comes from the installed distribution, which keeps
# pyproject.toml the only place the version is written.
try:
    __version__ = version("aiida-alc-ins")
except PackageNotFoundError:  # running from a source tree that is not installed
    __version__ = "0+unknown"
