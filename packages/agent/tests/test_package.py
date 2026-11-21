from importlib.resources import files

import trailcut_agent


def test_package_exposes_version() -> None:
    assert trailcut_agent.__version__ == "0.0.0"


def test_package_is_typed() -> None:
    assert files("trailcut_agent").joinpath("py.typed").is_file()
