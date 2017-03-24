import sys
from tomodachi.__version__ import __version__  # noqa
from tomodachi.cli import CLI


def cli_entrypoint(argv=None):
    if argv is None:
        argv = sys.argv
    return CLI().main(sys.argv[1:])
