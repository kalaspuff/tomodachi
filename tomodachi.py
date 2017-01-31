#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""tomodachi.py: microservice framework"""

import sys
import getopt
import logging
from tomodachi.container import ServiceContainer
from tomodachi.importer import ServiceImporter
from tomodachi.launcher import ServiceLauncher


class TomodachiCLI:
    def help_command(self):
        print('Usage: tomodachi.py subcommand [options] [args]')
        print()
        print('Options:')
        print('  -h, --help            show this help message and exit')
        print()
        print('Available subcommands:')
        print('  run <service ...>')
        print()
        sys.exit(2)

    def run_command(self, args):
        logging.basicConfig(format='%(asctime)s (%(name)s): %(message)s', level=logging.INFO)
        logging.Formatter(fmt='%(asctime)s.%(msecs).03d', datefmt='%Y-%m-%d %H:%M:%S')

        if len(args) == 0:
            print('Usage: tomodachi.py run <service ...>')
        else:
            services = set([ServiceContainer(ServiceImporter.import_service_file(arg)) for arg in set(args)])
            ServiceLauncher.run_until_complete(services)
        sys.exit(2)

    def main(self, argv):
        try:
            opts, args = getopt.getopt(argv, "h", ['help'])
        except getopt.GetoptError:
            self.help_command()
        for opt, arg in opts:
            if opt in ['-h', '--help']:
                self.help_command()
        if len(args):
            if args[0] == 'run':
                self.run_command(args[1:])
        self.help_command()


if __name__ == "__main__":
    cli = TomodachiCLI()
    cli.main(sys.argv[1:])
