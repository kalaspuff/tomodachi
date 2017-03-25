import tomodachi
import tomodachi.cli


def test_version():
    tomodachi.cli.CLI()
    assert tomodachi.__version__ == '0.1.5'
