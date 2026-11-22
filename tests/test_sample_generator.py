"""The committed sample must be exactly what scripts/make_sample.py generates."""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "make_sample", ROOT / "scripts" / "make_sample.py"
    )
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve annotations through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_committed_sample_matches_generator() -> None:
    gen = load_generator()
    committed = json.loads(gen.OUT.read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(gen.build()))


def test_generator_is_deterministic() -> None:
    gen = load_generator()
    assert json.dumps(gen.build()) == json.dumps(gen.build())


def test_committed_sample_market_matches_generator() -> None:
    gen = load_generator()
    committed = json.loads(gen.MARKET_OUT.read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(gen.build_market()))
