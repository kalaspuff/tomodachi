#!/usr/bin/env python
import asyncio
import getopt
import logging
import os
import sys
from typing import Dict, List, Optional

import tomodachi
from tomodachi.config import parse_config_files
from tomodachi.launcher import ServiceLauncher

try:
    if ModuleNotFoundError:
        pass
except Exception:

    class ModuleNotFoundError(ImportError):
        pass


class CLI:
    def help_command_usage(self) -> str:
        return (
            "Usage: tomodachi <command> [options] [arguments]\n"
            "\n"
            "Options:\n"
            "  -h, --help                                Show this help message and exit\n"
            "  -v, --version                             Print tomodachi version\n"
            "  --dependency-versions                     Print versions of dependencies\n"
            "\n"
            "Available commands:\n"
            "  ---\n"
            "  Command: run\n"
            "  Starts service(s) defined in the .py files specified as <service> argument(s)\n"
            "\n"
            "  $ tomodachi run <service ...> [-c <config-file ...>] [--production]\n"
            "  | --loop [auto|asyncio|uvloop]            Event loop implementation [asyncio]\n"
            "  | --production                            Disable restart on file changes\n"
            "  | -c, --config <files>                    Use configuration from JSON files\n"
            "  | -l, --log <level>, --log-level <level>  Specify log level\n"
            "\n"
            ">> Version: {}\n"
            ">> Full documentation at: https://tomodachi.dev/docs"
        ).format(tomodachi.__version__)

    def help_command(self) -> None:
        print(self.help_command_usage())
        sys.exit(2)

    def version_command(self) -> None:
        print("tomodachi {}".format(tomodachi.__version__))
        sys.exit(0)

    def dependency_versions_command(self) -> None:
        CLI.test_dependencies(fail_on_errors=False, output_versions=True, output_errors=True)
        sys.exit(0)

    @classmethod
    def test_dependencies(
        cls, fail_on_errors: bool = True, output_versions: bool = False, output_errors: bool = True
    ) -> Dict[str, Optional[str]]:
        errors = False

        aioamqp_version = ""
        aiobotocore_version = ""
        aiohttp_version = ""
        botocore_version = ""
        protobuf_version = ""
        uvloop_version = ""

        try:
            import aioamqp  # noqa  # isort:skip

            aioamqp_version = aioamqp.__version__
            if output_versions:
                print("aioamqp/{}".format(aioamqp_version))
        except ModuleNotFoundError as e:  # pragma: no cover
            errors = True
            if output_errors:
                print("Dependency failure: 'aioamqp' failed to load (error: \"{}\")".format(str(e)))
        except Exception as e:  # pragma: no cover
            errors = True
            if output_errors:
                print("Dependency failure: 'aioamqp' failed to load (error: \"{}\")".format(str(e)))
                logging.exception("")
                print("")

        try:
            import aiobotocore  # noqa  # isort:skip

            aiobotocore_version = aiobotocore.__version__
            if output_versions:
                print("aiobotocore/{}".format(aiobotocore_version))
        except ModuleNotFoundError as e:  # pragma: no cover
            errors = True
            if output_errors:
                print("Dependency failure: 'aiobotocore' failed to load (error: \"{}\")".format(str(e)))
        except Exception as e:  # pragma: no cover
            errors = True
            if output_errors:
                print("Dependency failure: 'aiobotocore' failed to load (error: \"{}\")".format(str(e)))
                logging.exception("")
                print("")

        try:
            import aiohttp  # noqa  # isort:skip

            aiohttp_version = aiohttp.__version__
            if output_versions:
                print("aiohttp/{}".format(aiohttp_version))
        except ModuleNotFoundError as e:  # pragma: no cover
            errors = True
            if output_errors:
                print("Dependency failure: 'aiohttp' failed to load (error: \"{}\")".format(str(e)))
        except Exception as e:  # pragma: no cover
            errors = True
            if output_errors:
                print("Dependency failure: 'aiohttp' failed to load (error: \"{}\")".format(str(e)))
                logging.exception("")
                print("")

        try:
            import botocore  # noqa  # isort:skip

            botocore_version = botocore.__version__
            if output_versions:
                print("botocore/{}".format(botocore_version))
        except ModuleNotFoundError as e:  # pragma: no cover
            errors = True
            if output_errors:
                print("Dependency failure: 'botocore' failed to load (error: \"{}\")".format(str(e)))
        except Exception as e:  # pragma: no cover
            errors = True
            if output_errors:
                print("Dependency failure: 'botocore' failed to load (error: \"{}\")".format(str(e)))
                logging.exception("")
                print("")

        try:
            # Optional
            import google.protobuf  # noqa  # isort:skip

            protobuf_version = (
                google.protobuf.__version__.decode()
                if isinstance(google.protobuf.__version__, bytes)
                else str(google.protobuf.__version__)
            )
            if output_versions:
                print("protobuf/{}".format(protobuf_version))
        except ModuleNotFoundError:  # pragma: no cover
            pass
        except Exception:  # pragma: no cover
            pass

        try:
            # Optional
            import uvloop  # noqa  # isort:skip

            uvloop_version = uvloop.__version__
            if output_versions:
                print("uvloop/{}".format(uvloop_version))
        except ModuleNotFoundError:  # pragma: no cover
            pass
        except Exception:  # pragma: no cover
            pass

        if not errors:
            try:
                import tomodachi.helpers.logging  # noqa  # isort:skip
                import tomodachi.invoker  # noqa  # isort:skip
                import tomodachi.transport.amqp  # noqa  # isort:skip
                import tomodachi.transport.aws_sns_sqs  # noqa  # isort:skip
                import tomodachi.transport.http  # noqa  # isort:skip
                import tomodachi.transport.schedule  # noqa  # isort:skip
            except Exception as e:  # pragma: no cover
                errors = True
                if output_errors:
                    print('Dependency failure: tomodachi essentials failed to load (error: "{}")'.format(str(e)))
                    logging.exception("")
                    print("")

        if errors:
            if fail_on_errors:
                logging.getLogger("exception").warning("Unable to initialize dependencies")
                logging.getLogger("exception").warning("Error: See above exceptions and traceback")
                sys.exit(1)
            elif output_errors:
                print("There were errors - see above for exceptions and traceback")

        return {
            "aioamqp": aioamqp_version or None,
            "aiobotocore": aiobotocore_version or None,
            "aiohttp": aiohttp_version or None,
            "botocore": botocore_version or None,
            "protobuf": protobuf_version or None,
            "uvloop": uvloop_version or None,
        }

    def run_command_usage(self) -> str:
        return "Usage: tomodachi run <service ...> [-c <config-file ...>] [--loop auto|asyncio|uvloop] [--production]"

    def run_command(self, args: List[str]) -> None:
        if len(args) == 0:
            print(self.run_command_usage())
        else:
            configuration = None
            log_level = logging.INFO

            if "--loop" in args:
                index = args.index("--loop")
                args.pop(index)
                value = args.pop(index).lower()

                if value in ("auto", "default"):
                    pass
                elif value in ("asyncio", "aio", "async"):
                    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
                    pass
                elif value in ("uvloop", "libuv", "uv"):
                    try:
                        import uvloop  # noqa  # isort:skip
                    except Exception:  # pragma: no cover
                        print("The 'uvloop' package needs to be installed to use uvloop event loop")
                        sys.exit(2)
                    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
                else:
                    print("Invalid argument to --loop, event loop '{}' not recognized".format(value))
                    sys.exit(2)

            if "-c" in args or "--config" in args:
                index = args.index("-c") if "-c" in args else args.index("--config")
                args.pop(index)

                config_files: List[str] = []
                while len(args) > index and args[index][0] != "-":
                    value = args.pop(index)
                    if value not in config_files:
                        config_files.append(value)

                if not len(config_files):
                    print("Missing config file on command line")
                    sys.exit(2)

                try:
                    configuration = parse_config_files(config_files)
                except FileNotFoundError as e:
                    print("Invalid config file: {}".format(str(e)))
                    sys.exit(2)
                except ValueError as e:
                    print("Invalid config file, invalid JSON format: {}".format(str(e)))
                    sys.exit(2)

            if "--production" in args:
                index = args.index("--production")
                args.pop(index)
                watcher = None
            else:
                cwd = os.getcwd()
                root_directories = [os.getcwd()]
                for arg in set(args):
                    root_directories.append(os.path.dirname("{}/{}".format(os.path.realpath(cwd), arg)))
                from tomodachi.watcher import Watcher  # noqa  #  isort:skip

                watcher = Watcher(root=root_directories, configuration=configuration)

            if "-l" in args or "--log" in args or "--log-level" in args:
                index = (
                    args.index("-l")
                    if "-l" in args
                    else args.index("--log")
                    if "--log" in args
                    else args.index("--log-level")
                )
                args.pop(index)
                if len(args) > index:
                    log_level = getattr(logging, args.pop(index).upper(), None) or log_level

            logging.basicConfig(format="%(asctime)s (%(name)s): %(message)s", level=log_level)
            logging.Formatter(fmt="%(asctime)s.%(msecs).03d", datefmt="%Y-%m-%d %H:%M:%S")

            ServiceLauncher.run_until_complete(set(args), configuration, watcher)
        sys.exit(0)

    def main(self, argv: List[str]) -> None:
        try:
            opts, args = getopt.getopt(
                argv, "hlvV ", ["help", "log", "version", "version", "dependency-versions", "dependencies", "deps"]
            )
        except getopt.GetoptError:
            self.help_command()
        for opt, _ in opts:
            if opt in ("-h", "--help"):
                self.help_command()
            if opt in ("-v", "-V", "--version"):
                self.version_command()
            if opt in ("--dependency-versions", "--dependencies", "--deps"):
                self.dependency_versions_command()
        if len(args):
            if args[0] in ("run", "start", "go"):
                self.run_command(args[1:])
        self.help_command()


def cli_entrypoint(argv: Optional[List[str]] = None) -> None:
    if argv is None:
        argv = sys.argv
        if argv[0].endswith("pytest"):
            argv = ["tomodachi"]

    CLI().main(argv[1:])
