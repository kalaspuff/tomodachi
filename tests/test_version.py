import tomodachi


def test_version_exists() -> None:
    assert tomodachi.__version__ is not None
    assert isinstance(tomodachi.__version__, tuple)
