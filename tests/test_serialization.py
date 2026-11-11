"""Tests for the serializer/deserializer registry in `serialization.py`."""

from __future__ import annotations

import importlib

import pytest

from aiida_alc_ins.serialization import EUPHONIC_SERIALIZERS


@pytest.mark.parametrize("key", list(EUPHONIC_SERIALIZERS))
def test_serializer_key_resolves_to_an_importable_class(key):
    """Every EUPHONIC_SERIALIZERS key names a real, importable class.

    A key is a dotted ``module.ClassName`` path. Guards against Decision 10's
    failure mode: a stale key does not raise at lookup time, it silently falls
    through to a generic ``JsonableData`` fallback, so this must be checked
    explicitly rather than relying on ``aiida-pythonjob`` to fail loudly.
    """
    module_name, _, class_name = key.rpartition(".")
    module = importlib.import_module(module_name)
    resolved = getattr(module, class_name)

    assert f"{resolved.__module__}.{resolved.__name__}" == key
