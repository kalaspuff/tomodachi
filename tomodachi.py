#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""tomodachi.py: microservice framework"""

import sys
import getopt
import logging
from tomodachi.launcher import ServiceLauncher
from tomodachi.watcher import Watcher
from tomodachi.config import parse_config_files


class TomodachiCLI:
    def help_command(self):
        print('Usage: tomodachi.py subcommand [options] [args]')
        print()
        print('Options:')
        print('  -h, --help            show this help message and exit')
        print()
        print('Available subcommands:')
        print('  run <service ...> [-c <config-file ...>] [--production]')
        print('  -c, --config          use json configuration files')
        print('  --production          disable restart on file changes')
        print()
        sys.exit(2)

    def run_command(self, args):
        logging.basicConfig(format='%(asctime)s (%(name)s): %(message)s', level=logging.INFO)
        logging.Formatter(fmt='%(asctime)s.%(msecs).03d', datefmt='%Y-%m-%d %H:%M:%S')

        if len(args) == 0:
            print('Usage: tomodachi.py run <service ...> [-c <config-file ...>] [--production]')
        else:
            configuration = None
            if '-c' in args or '--config' in args:
                index = args.index('-c') or args.index('--config')
                args.pop(index)

                config_files = []
                while len(args) > index and args[index][0] != '-':
                    value = args.pop(index)
                    if value not in config_files:
                        config_files.append(value)

                if not len(config_files):
                    print('Missing config file on command line')
                    sys.exit(2)

                try:
                    configuration = parse_config_files(config_files)
                except FileNotFoundError as e:
                    print('Invalid config file: {}'.format(str(e)))
                    sys.exit(2)

            if '--production' in args:
                index = args.index('--production')
                args.pop(index)
                watcher = None
            else:
                watcher = Watcher()
            ServiceLauncher.run_until_complete(set(args), configuration, watcher)
        sys.exit(0)

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
