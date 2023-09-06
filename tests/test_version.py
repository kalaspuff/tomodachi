import tomodachi


def test_version_exists() -> None:
    assert tomodachi.__version__ is not None
    assert isinstance(tomodachi.__version__, str)
    assert isinstance(tomodachi.__version_info__, tuple)
