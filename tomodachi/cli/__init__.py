#!/usr/bin/env python
import os
import sys
import getopt
import logging
from typing import List, Optional
from tomodachi.launcher import ServiceLauncher
from tomodachi.watcher import Watcher
from tomodachi.config import parse_config_files


class CLI:
    def help_command_usage(self) -> str:
        return ('Usage: tomodachi.py subcommand [options] [args]\n'
                '\n'
                'Options:\n'
                '  -h, --help            show this help message and exit\n'
                '\n'
                'Available subcommands:\n'
                '  run <service ...> [-c <config-file ...>] [--production]\n'
                '  -c, --config          use json configuration files\n'
                '  --production          disable restart on file changes\n'
                '\n'
                )

    def help_command(self) -> None:
        print(self.help_command_usage())
        sys.exit(2)

    def run_command_usage(self) -> str:
        return 'Usage: tomodachi.py run <service ...> [-c <config-file ...>] [--production]'

    def run_command(self, args: List[str]) -> None:
        logging.basicConfig(format='%(asctime)s (%(name)s): %(message)s', level=logging.INFO)
        logging.Formatter(fmt='%(asctime)s.%(msecs).03d', datefmt='%Y-%m-%d %H:%M:%S')

        if len(args) == 0:
            print(self.run_command_usage())
        else:
            configuration = None
            if '-c' in args or '--config' in args:
                index = args.index('-c') if '-c' in args else args.index('--config')
                args.pop(index)

                config_files = []  # type: List[str]
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
                except ValueError as e:
                    print('Invalid config file, invalid JSON format: {}'.format(str(e)))
                    sys.exit(2)

            if '--production' in args:
                index = args.index('--production')
                args.pop(index)
                watcher = None
            else:
                cwd = os.getcwd()
                root_directories = [os.getcwd()]
                for arg in set(args):
                    root_directories.append(os.path.dirname('{}/{}'.format(os.path.realpath(cwd), arg)))
                watcher = Watcher(root=root_directories, configuration=configuration)
            ServiceLauncher.run_until_complete(set(args), configuration, watcher)
        sys.exit(0)

    def main(self, argv: List[str]) -> None:
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


def cli_entrypoint(argv: Optional[List[str]]=None) -> None:
    if argv is None:
        argv = sys.argv
    CLI().main(argv[1:])
