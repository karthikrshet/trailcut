from importlib.resources import files

import trailcut_ingest


def test_package_exposes_version() -> None:
    assert trailcut_ingest.__version__ == "0.0.0"


def test_package_is_typed() -> None:
    assert files("trailcut_ingest").joinpath("py.typed").is_file()
