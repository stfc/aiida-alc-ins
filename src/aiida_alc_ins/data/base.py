"""Shared base class for AiiDA Data nodes that wrap a Euphonic object.

Euphonic's core objects (``ForceConstants``, ``QpointPhononModes``, ...) all
expose a public JSON round-trip (``obj.to_json_file(path)`` /
``Cls.from_json_file(path)``); see
https://euphonic.readthedocs.io/en/stable/ .

We reuse that public serialisation and store the resulting JSON inside the AiiDA
node's *repository* (file store) rather than the database, because force-constants
arrays can be large. This keeps the DB light while preserving full provenance.

AiiDA Data / repository API reference:
https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/data_types.html
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, ClassVar, Self

from aiida.orm import Data


class EuphonicJSONData(Data):
    """Store a single Euphonic object as JSON in the node repository.

    Subclasses set :attr:`_euphonic_cls` (the wrapped Euphonic class). The object
    is written on construction and read back lazily via :meth:`get_object`.
    """

    # Set by subclasses, e.g. ``euphonic.ForceConstants``.
    _euphonic_cls: ClassVar[type | None] = None

    # Repository object key: the name the JSON blob is stored under (and read back
    # from) in the node's file repository. Only needs to be *stable*, not unique
    # per class -- the node type and the JSON's own ``__euphonic_class__`` already
    # identify the object -- so a single shared name suffices for all subclasses.
    _filename: ClassVar[str] = "euphonic_object.json"

    def __init__(self, euphonic_object: Any | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        if euphonic_object is not None:
            self._set_object(euphonic_object)

    def _set_object(self, euphonic_object: Any) -> None:
        """Validate and serialise ``euphonic_object`` into the repository."""
        self._validate_type(euphonic_object)
        # Euphonic only serialises to/from a filesystem path, so bounce through a
        # temporary file and hand the bytes to the AiiDA repository.
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / self._filename
            euphonic_object.to_json_file(str(tmp_path))
            self.base.repository.put_object_from_file(str(tmp_path), self._filename)

    def _validate_type(self, euphonic_object: Any) -> None:
        """Raise ``TypeError`` unless the object matches :attr:`_euphonic_cls`."""
        if self._euphonic_cls is not None and not isinstance(
            euphonic_object, self._euphonic_cls
        ):
            msg = (
                f"Expected a {self._euphonic_cls.__name__} instance, "
                f"got {type(euphonic_object).__name__}."
            )
            raise TypeError(msg)

    def get_object(self) -> Any:
        """Reconstruct and return the wrapped Euphonic object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / self._filename
            with self.base.repository.open(self._filename, mode="rb") as handle:
                tmp_path.write_bytes(handle.read())
            return self._euphonic_cls.from_json_file(str(tmp_path))

    @classmethod
    def from_json_file(cls, filepath: str | Path) -> Self:
        """Build a node directly from an existing Euphonic JSON file."""
        node = cls()
        node.base.repository.put_object_from_file(str(filepath), cls._filename)
        return node
