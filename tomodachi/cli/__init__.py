#!/usr/bin/env python
import asyncio
import getopt
import logging
import os
import sys
from typing import Dict, List, Literal, Optional, Tuple, Union, cast

import tomodachi
from tomodachi.config import parse_config_files
from tomodachi.helpers.build_time import get_time_since_build
from tomodachi.launcher import ServiceLauncher


class CLI:
    def help_command_usage(self) -> str:
        from tomodachi.helpers.colors import COLOR, COLOR_RESET, COLOR_STYLE

        LABEL = f"{COLOR_RESET}{COLOR.YELLOW}{COLOR_STYLE.BRIGHT}"
        SHELL = f"{COLOR_RESET}{COLOR.WHITE}{COLOR_STYLE.DIM}"
        MAIN_USAGE = f"{COLOR_RESET}{COLOR.WHITE}{COLOR_STYLE.BRIGHT}"
        AVAILABLE_COMMAND = f"{COLOR_RESET}{COLOR.BLUE}"
        OPTION = f"{COLOR_RESET}{COLOR.GREEN}"
        DEFAULT = f"{COLOR_RESET}{COLOR.WHITE}{COLOR_STYLE.DIM}"
        BOTTOM_TEXT = f"{COLOR_RESET}{COLOR.LIGHTBLACK_EX}"
        BOTTOM_LABEL = f"{COLOR_RESET}{COLOR.WHITE}{COLOR_STYLE.DIM}"

        time_since_tomodachi_build = get_time_since_build() or "local development version"
        return (
            f"{LABEL}usage:{COLOR_RESET}\n"
            f"  {SHELL}${COLOR_RESET} {MAIN_USAGE}tomodachi run [options] <service.py ...>{COLOR_RESET}\n"
            "\n"
            f"{LABEL}description:{COLOR_RESET}\n"
            f"  starts the tomodachi service(s) defined in the files provided as arguments.\n"
            "\n"
            f"{LABEL}options:{COLOR_RESET}\n"
            f"  {OPTION}--loop [auto|asyncio|uvloop]{COLOR_RESET}\n"
            f"      use the specified event loop implementation. {DEFAULT}(default: auto){COLOR_RESET}\n"
            f"  {OPTION}--production{COLOR_RESET}\n"
            "      disables service restart on file changes and hides the info banner.\n"
            f"  {OPTION}--log-level [debug|info|warning|error|critical]{COLOR_RESET}\n"
            f"      specify the minimum log level. {DEFAULT}(default: info){COLOR_RESET}\n"
            f"  {OPTION}--logger [console|json|python|disabled]{COLOR_RESET}\n"
            f"      specify a log formatter for tomodachi.logging. {DEFAULT}(default: console){COLOR_RESET}\n"
            f"  {OPTION}--custom-logger <module.attribute|module>{COLOR_RESET}\n"
            "      use a custom logger object or custom log module (as import path).\n"
            f"  {OPTION}--opentelemetry-instrument{COLOR_RESET}\n"
            "      auto-instruments the application with opentelemetry instrumentors.\n"
            "\n"
            f"{LABEL}usage examples:{COLOR_RESET}\n"
            f"  {SHELL}${COLOR_RESET} {AVAILABLE_COMMAND}tomodachi run --production --logger json --loop uvloop service/app.py{COLOR_RESET}\n"
            f"  {SHELL}${COLOR_RESET} {AVAILABLE_COMMAND}tomodachi run --log-level warning --custom-logger foobar.logger service.py{COLOR_RESET}\n"
            "\n"
            f"{BOTTOM_LABEL}ver{COLOR_RESET} {BOTTOM_TEXT}{tomodachi.__version__} ({time_since_tomodachi_build}){COLOR_RESET}\n"
            f"{BOTTOM_LABEL}git{COLOR_RESET} {BOTTOM_TEXT}https://github.com/kalaspuff/tomodachi{COLOR_RESET}\n"
        )

    def help_command(self) -> None:
        print(self.help_command_usage())
        sys.exit(0)

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
        opentelemetry_api_version = ""
        opentelemetry_sdk_version = ""
        opentelemetry_instrumentation_version = ""

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

            protobuf_version_ = google.protobuf.__version__
            if isinstance(protobuf_version_, bytes):  # type: ignore
                protobuf_version = cast(bytes, protobuf_version_).decode()  # type: ignore
            else:
                protobuf_version = str(protobuf_version_)
            if output_versions:
                print("protobuf/{}".format(protobuf_version))
        except ModuleNotFoundError:  # pragma: no cover
            pass
        except Exception:  # pragma: no cover
            pass

        try:
            # Optional
            import uvloop  # noqa  # isort:skip

            uvloop_version = str(getattr(uvloop, "__version__", ""))
            if output_versions:
                print("uvloop/{}".format(uvloop_version))
        except ModuleNotFoundError:  # pragma: no cover
            pass
        except Exception:  # pragma: no cover
            pass

        try:
            # Optional
            import opentelemetry.instrumentation.version  # noqa  # isort:skip
            import opentelemetry.sdk.version  # noqa  # isort:skip
            import opentelemetry.version  # noqa  # isort:skip

            opentelemetry_api_version = opentelemetry.version.__version__
            opentelemetry_sdk_version = opentelemetry.sdk.version.__version__
            opentelemetry_instrumentation_version = opentelemetry.instrumentation.version.__version__
            if output_versions:
                print("opentelemetry-api/{}".format(opentelemetry_api_version))
                print("opentelemetry-sdk/{}".format(opentelemetry_sdk_version))
                print("opentelemetry-instrumentation/{}".format(opentelemetry_instrumentation_version))
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
            "opentelemetry-api": opentelemetry_api_version or None,
            "opentelemetry-sdk": opentelemetry_sdk_version or None,
            "opentelemetry-instrumentation": opentelemetry_instrumentation_version or None,
        }

    def run_command(self, args: List[str]) -> None:
        if len(args) == 0:
            print(self.help_command_usage())
        else:
            configuration = None
            log_level = logging.INFO

            tomodachi.get_contextvar("run.args").set(args[:])

            # --loop (env: TOMODACHI_LOOP)
            env_loop = str(os.getenv("TOMODACHI_LOOP", "")).lower() or None

            if env_loop or "--loop" in args:
                if "--loop" in args:
                    index = args.index("--loop")
                    args.pop(index)
                    value = args.pop(index).lower()

                    if env_loop and env_loop != value:
                        print("Invalid value for --loop option: '{}' differs from env TOMODACHI_LOOP".format(value))
                        sys.exit(2)
                elif env_loop:
                    value = env_loop
                else:
                    value = "auto"

                if value in ("auto", "default"):
                    value = "auto"
                elif value in ("asyncio", "aio", "async"):
                    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
                    value = "asyncio"
                elif value in ("uvloop", "libuv", "uv"):
                    try:
                        import uvloop  # noqa  # isort:skip
                    except Exception:  # pragma: no cover
                        print("The 'uvloop' package needs to be installed to use uvloop event loop")
                        sys.exit(2)
                    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
                    value = "uvloop"
                else:
                    print("Invalid value for --loop option: '{}' not recognized".format(value))
                    sys.exit(2)

                tomodachi.get_contextvar("loop.setting").set(value)
            else:
                tomodachi.get_contextvar("loop.setting").set("auto")

            # --config
            if "-c" in args or "--config" in args:
                import warnings  # isort:skip

                warnings.warn(
                    "Using the -c (--config) CLI argument is deprecated. Set and parse service config with environment variables instead.",
                    DeprecationWarning,
                )

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

            # --production (env: TOMODACHI_PRODUCTION)
            env_production = str(os.getenv("TOMODACHI_PRODUCTION", "")).lower() or None
            if env_production and env_production in ("0", "no", "none", "false"):
                env_production = None

            if env_production or "--production" in args:
                if "--production" in args:
                    index = args.index("--production")
                    args.pop(index)
                watcher = None
            else:
                cwd = os.path.realpath(os.getcwd())
                root_directories = [cwd]
                for arg in set(args):
                    if not arg.startswith("/") and not arg.startswith("~"):
                        root_directories.append(os.path.realpath(os.path.dirname(os.path.join(cwd, arg))))
                    else:
                        root_directories.append(os.path.realpath(os.path.dirname(arg)))
                for p in str(os.getenv("PYTHONPATH", "")).split(os.pathsep):
                    if not p:
                        continue
                    if not p.startswith("/") and not p.startswith("~"):
                        root_directories.append(os.path.realpath(os.path.join(cwd, p)))
                    else:
                        root_directories.append(os.path.realpath(p))

                from tomodachi.watcher import Watcher  # noqa  #  isort:skip

                watcher = Watcher(root=root_directories, configuration=configuration)

            # --log-level (env: TOMODACHI_LOG_LEVEL)
            env_log_level: Optional[Union[str, int]] = str(os.getenv("TOMODACHI_LOG_LEVEL", "")).lower() or None
            if not env_log_level:
                env_log_level = None

            if env_log_level is not None:
                log_level_ = getattr(logging, str(env_log_level).upper(), None) or logging.NOTSET
                if type(log_level_) is not int or log_level_ == logging.NOTSET:
                    print(
                        "Invalid TOMODACHI_LOG_LEVEL environment value (expected 'debug', 'info', 'warning', 'error' or 'critical')"
                    )
                    sys.exit(2)
                env_log_level = log_level_

            if "-l" in args or "--log" in args or "--log-level" in args:
                index = (
                    args.index("-l")
                    if "-l" in args
                    else args.index("--log") if "--log" in args else args.index("--log-level")
                )
                args.pop(index)
                if len(args) > index:
                    arg_value = args.pop(index)
                    log_level_ = getattr(logging, arg_value.upper(), None) or logging.NOTSET
                    if type(log_level_) is not int or log_level_ == logging.NOTSET:
                        print(
                            "Invalid log level: '{}' (expected 'debug', 'info', 'warning', 'error' or 'critical')".format(
                                arg_value
                            )
                        )
                        sys.exit(2)

                    if env_log_level is not None and env_log_level != log_level_:
                        print(
                            "Invalid value for --log-level option: '{}' differs from env TOMODACHI_LOG_LEVEL".format(
                                value
                            )
                        )
                        sys.exit(2)

                    log_level = log_level_
            elif env_log_level and type(env_log_level) is int:
                log_level = env_log_level

            # --logger (env: TOMODACHI_LOGGER)
            env_logger = cast(
                Optional[Literal["json", "console", "custom", "python", "disabled"]],
                str(os.getenv("TOMODACHI_LOGGER", "")).lower() or None,
            )
            if not env_logger:
                env_logger = None

            if env_logger or "--logger" in args:
                if "--logger" in args:
                    index = args.index("--logger")
                    args.pop(index)
                    try:
                        value = args.pop(index).lower()
                    except IndexError:
                        print("Missing value for --logger option")
                        sys.exit(2)

                    if env_logger and env_logger != value:
                        print("Invalid value for --logger option: '{}' differs from env TOMODACHI_LOGGER".format(value))
                        sys.exit(2)
                else:
                    value = env_logger or ""

                if value not in ("json", "console", "custom", "python", "disabled"):
                    print(
                        "Invalid value for --logger option: '{}' (expected 'json', 'console', 'python' or 'disabled')".format(
                            value
                        )
                    )
                    sys.exit(2)

                env_logger = cast(Literal["json", "console", "custom", "python", "disabled"], value)

            if not env_logger:
                env_logger = None

            # --custom-logger (env: TOMODACHI_CUSTOM_LOGGER)
            env_custom_logger = str(os.getenv("TOMODACHI_CUSTOM_LOGGER", "")).lower() or None
            if not env_custom_logger:
                env_custom_logger = None

            if env_custom_logger or "--custom-logger" in args:
                if "--custom-logger" in args:
                    index = args.index("--custom-logger")
                    args.pop(index)
                    try:
                        value = args.pop(index)
                    except IndexError:
                        print("Missing value for --custom-logger option")
                        sys.exit(2)

                    if env_custom_logger and env_custom_logger != value:
                        print(
                            "Invalid value for --custom-logger option: '{}' differs from env TOMODACHI_CUSTOM_LOGGER".format(
                                value
                            )
                        )
                        sys.exit(2)
                else:
                    value = env_custom_logger or ""

                if env_logger and env_logger != "custom":
                    print("Invalid combination of --custom-logger and --logger options")
                    sys.exit(2)

                env_custom_logger = value
                env_logger = "custom"

            if env_logger and env_logger == "custom" and not env_custom_logger:
                print("Invalid combination of --custom-logger and --logger options")
                sys.exit(2)

            # --opentelemetry-instrument (env: TOMODACHI_OPENTELEMETRY_INSTRUMENT)
            env_opentelemetry_instrument = str(os.getenv("TOMODACHI_OPENTELEMETRY_INSTRUMENT", "")).lower() or None
            if env_opentelemetry_instrument and env_opentelemetry_instrument in ("0", "no", "none", "false"):
                env_opentelemetry_instrument = None

            if env_opentelemetry_instrument or "--opentelemetry-instrument" in args:
                if "--opentelemetry-instrument" in args:
                    index = args.index("--opentelemetry-instrument")
                    args.pop(index)

                try:
                    import opentelemetry.instrumentation.auto_instrumentation._load  # noqa  # isort:skip
                    import opentelemetry.util.http  # noqa  # isort:skip
                    import opentelemetry.sdk.version  # noqa  # isort:skip
                    import opentelemetry.version  # noqa  # isort:skip
                except Exception:  # pragma: no cover
                    print("The 'opentelemetry' extras needs to be installed to use OpenTelemetry instrumentation")
                    sys.exit(2)

                auto_instrument_opentelemetry = True
            else:
                auto_instrument_opentelemetry = False

            if not args:
                from tomodachi.helpers.colors import COLOR, COLOR_RESET, COLOR_STYLE

                print(f"{COLOR.RED}error:{COLOR_RESET} no service file has been provided as argument.")

                print("")
                print(f"{COLOR.WHITE}{COLOR_STYLE.DIM}---{COLOR_RESET}")
                print("")

                print("use the '--help' option for cli usage help.")
                print(f"{COLOR.WHITE}{COLOR_STYLE.DIM}${COLOR_RESET} {COLOR.BLUE}tomodachi --help{COLOR_RESET}")
                sys.exit(2)

            if auto_instrument_opentelemetry:
                from tomodachi.opentelemetry.auto_instrumentation import initialize as initialize_opentelemetry

                try:
                    initialize_opentelemetry()
                except Exception:
                    logging.getLogger("tomodachi.opentelemetry").exception("Failed to auto initialize opentelemetry")

            tomodachi.logging.set_default_formatter(env_logger)
            tomodachi.logging.set_custom_logger_factory(env_custom_logger)
            tomodachi.logging.configure(log_level=log_level)

            ServiceLauncher.run_until_complete(set(args), configuration, watcher)

        # Cleanup log handlers
        tomodachi.logging.remove_handlers()

        sys.exit(tomodachi.SERVICE_EXIT_CODE)

    def main(self, argv: List[str]) -> None:
        opts: List[Tuple[str, str]] = []
        args: List[str] = []

        try:
            opts, args = getopt.getopt(
                argv,
                "hlvV ",
                [
                    "help",
                    "log",
                    "version",
                    "version",
                    "dependency-versions",
                    "dependencies",
                    "deps",
                    "logger",
                    "log-level",
                    "custom-logger",
                    "production",
                    "loop",
                ],
            )
        except getopt.GetoptError as e:
            from tomodachi.helpers.colors import COLOR, COLOR_RESET, COLOR_STYLE

            print(f"{COLOR.RED}error:{COLOR_RESET} invalid command or combination of command options.")
            print(f"{COLOR.RED}error:{COLOR_RESET} {str(e)}.")

            print("")
            print(f"{COLOR.WHITE}{COLOR_STYLE.DIM}---{COLOR_RESET}")
            print("")

            print("use the '--help' option for cli usage help.")
            print(f"{COLOR.WHITE}{COLOR_STYLE.DIM}${COLOR_RESET} {COLOR.BLUE}tomodachi --help{COLOR_RESET}")
            sys.exit(2)
        for opt, _ in opts:
            if opt in ("-h", "--help"):
                self.help_command()
            if opt in ("-v", "-V", "--version"):
                self.version_command()
            if opt in ("--dependency-versions", "--dependencies", "--deps"):
                self.dependency_versions_command()

            if opt in ("-l", "--log-level", "--log", "--logger", "--custom-logger", "--production", "--loop"):
                from tomodachi.helpers.colors import COLOR, COLOR_RESET, COLOR_STYLE

                print(f"{COLOR.RED}error:{COLOR_RESET} invalid command or combination of command options.")
                print(f"{COLOR.RED}error:{COLOR_RESET} the command 'run' must be specified before any options.")

                print("")
                print(f"{COLOR.WHITE}{COLOR_STYLE.DIM}---{COLOR_RESET}")
                print("")

                if any([a.endswith(".py") for a in argv]):
                    new_args = ["run"] + [a for a in argv if a not in ("run", "start", "go")]
                    print("maybe you intended to run something like this?")
                    print(
                        f"{COLOR.WHITE}{COLOR_STYLE.DIM}${COLOR_RESET} {COLOR.BLUE}tomodachi {' '.join(new_args)}{COLOR_RESET}"
                    )
                    print("")

                print("use the '--help' option for cli usage help.")
                print(f"{COLOR.WHITE}{COLOR_STYLE.DIM}${COLOR_RESET} {COLOR.BLUE}tomodachi --help{COLOR_RESET}")
                sys.exit(2)

        if len(args):
            if args[0] in ("run", "start", "go"):
                self.run_command(args[1:])

        if args or opts:
            from tomodachi.helpers.colors import COLOR, COLOR_RESET, COLOR_STYLE

            print(f"{COLOR.RED}error:{COLOR_RESET} invalid command or combination of command options.")
            print(
                f"{COLOR.RED}error:{COLOR_RESET} the command 'run' must be specified before any service files or options."
            )

            print("")
            print(f"{COLOR.WHITE}{COLOR_STYLE.DIM}---{COLOR_RESET}")
            print("")

            if any([a.endswith(".py") for a in argv]):
                new_args = ["run"] + [a for a in argv]
                print("maybe you intended to run something like this?")
                print(
                    f"{COLOR.WHITE}{COLOR_STYLE.DIM}${COLOR_RESET} {COLOR.BLUE}tomodachi {' '.join(new_args)}{COLOR_RESET}"
                )
                print("")

            print("use the '--help' option for cli usage help.")
            print(f"{COLOR.WHITE}{COLOR_STYLE.DIM}${COLOR_RESET} {COLOR.BLUE}tomodachi --help{COLOR_RESET}")
            sys.exit(2)

        self.help_command()


def cli_entrypoint(argv: Optional[List[str]] = None) -> None:
    if argv is None:
        argv = sys.argv
        if argv[0].endswith("pytest"):
            argv = ["tomodachi"]

    CLI().main(argv[1:])
