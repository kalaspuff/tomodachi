import asyncio
import inspect
import logging
import os
import re
import sys
import types
import uuid
from types import ModuleType, TracebackType
from typing import Any, Dict, Optional, Set, cast

import tomodachi
from tomodachi import CLASS_ATTRIBUTE
from tomodachi.config import merge_dicts
from tomodachi.helpers.execution_context import set_service, unset_service
from tomodachi.invoker import FUNCTION_ATTRIBUTE, INVOKER_TASK_START_KEYWORD, START_ATTRIBUTE


class ServiceContainer(object):
    def __init__(self, module_import: ModuleType, configuration: Optional[Dict] = None) -> None:
        self.module_import = module_import

        self.file_path = module_import.__file__
        self.module_name = (
            module_import.__name__.rsplit("/", 1)[1] if "/" in module_import.__name__ else module_import.__name__
        ).rsplit(".", 1)[-1]
        self.configuration = configuration
        self.logger = logging.getLogger("services.{}".format(self.module_name))

        self._close_waiter: asyncio.Future = asyncio.Future()
        self.started_waiter: asyncio.Future = asyncio.Future()

        def catch_uncaught_exceptions(type_: type, value: BaseException, traceback: TracebackType) -> None:
            raise value

        sys.excepthook = catch_uncaught_exceptions

    def stop_service(self) -> None:
        if not self._close_waiter.done():
            self._close_waiter.set_result(None)

    def setup_configuration(self, instance: Any) -> None:
        if not self.configuration:
            return
        for k, v in self.configuration.items():
            instance_value = getattr(instance, k, None)
            if not instance_value:
                setattr(instance, k, v)

            if isinstance(instance_value, list) and isinstance(v, list):
                setattr(instance, k, instance_value + v)
            elif isinstance(instance_value, dict) and isinstance(v, dict):
                setattr(instance, k, merge_dicts(instance_value, v))
            else:
                setattr(instance, k, v)

    async def wait_stopped(self) -> None:
        await self._close_waiter

    async def run_until_complete(self) -> None:
        services_started: Set = set()
        invoker_tasks: Set = set()
        start_futures: Set = set()
        stop_futures: Set = set()
        started_futures: Set = set()
        registered_services: Set = set()
        for _, cls in inspect.getmembers(self.module_import):
            if inspect.isclass(cls):
                if not getattr(cls, CLASS_ATTRIBUTE, False):
                    continue

                instance = cls()
                if not getattr(instance, "context", None):
                    setattr(
                        instance,
                        "context",
                        {
                            i: getattr(instance, i)
                            for i in dir(instance)
                            if not callable(i)
                            and not i.startswith("__")
                            and not isinstance(getattr(instance, i), types.MethodType)
                        },
                    )

                getattr(instance, "context", {})["_service_file_path"] = self.file_path

                self.setup_configuration(instance)

                context_options = getattr(instance, "context", {}).get("options", {})
                if context_options:
                    for key in list(context_options.keys()):
                        if "." in key:
                            key_split = key.split(".")
                            op_lvl = context_options
                            for i, k_lvl in enumerate(key_split):
                                if i + 1 == len(key_split):
                                    if k_lvl in op_lvl and op_lvl[k_lvl] != context_options[key]:
                                        raise Exception(
                                            'Missmatching options for \'{}\': ({}) "{}" and ({}) "{}" differs'.format(
                                                key,
                                                type(context_options[key]).__name__,
                                                context_options[key],
                                                type(op_lvl[k_lvl]).__name__,
                                                op_lvl[k_lvl],
                                            )
                                        )
                                    op_lvl[k_lvl] = context_options[key]
                                    continue
                                if k_lvl not in op_lvl:
                                    op_lvl[k_lvl] = {}
                                op_lvl = op_lvl.get(k_lvl)

                if not getattr(instance, "uuid", None):
                    instance.uuid = str(uuid.uuid4())

                service_name = getattr(instance, "name", getattr(cls, "name", None))

                if not service_name:
                    service_name = ServiceContainer.assign_service_name(instance)
                    if not service_name:
                        continue

                set_service(service_name, instance)

                log_level = getattr(instance, "log_level", None) or getattr(cls, "log_level", None) or "INFO"

                def invoker_function_sorter(m: str) -> int:
                    for i, line in enumerate(inspect.getsourcelines(self.module_import)[0]):
                        if re.match(r"^\s*(async)?\s+def\s+{}\s*([(].*$)?$".format(m), line):
                            return i
                    return -1

                invoker_functions = []
                for name, fn in inspect.getmembers(cls):
                    if inspect.isfunction(fn) and getattr(fn, FUNCTION_ATTRIBUTE, None):
                        setattr(fn, START_ATTRIBUTE, True)  # deprecated
                        invoker_functions.append(name)
                invoker_functions.sort(key=invoker_function_sorter)
                if invoker_functions:
                    invoker_tasks = invoker_tasks | set(
                        [
                            asyncio.ensure_future(getattr(instance, name)(**{INVOKER_TASK_START_KEYWORD: True}))
                            for name in invoker_functions
                        ]
                    )
                    services_started.add((service_name, instance, log_level))

                try:
                    start_futures.add(getattr(instance, "_start_service"))
                    services_started.add((service_name, instance, log_level))
                except AttributeError:
                    pass

                if getattr(instance, "_started_service", None):
                    services_started.add((service_name, instance, log_level))

        if services_started:
            try:
                for name, instance, log_level in services_started:
                    self.logger.info('Initializing service "{}" [id: {}]'.format(name, instance.uuid))

                if start_futures:
                    start_task_results = await asyncio.wait(
                        [asyncio.ensure_future(func()) for func in start_futures if func]
                    )
                    exception = [
                        v.exception() for v in [value for value in start_task_results if value][0] if v.exception()
                    ]
                    if exception:
                        raise cast(Exception, exception[0])
                if invoker_tasks:
                    task_results = await asyncio.wait(
                        [asyncio.ensure_future(func()) for func in (await asyncio.gather(*invoker_tasks)) if func]
                    )
                    exception = [v.exception() for v in [value for value in task_results if value][0] if v.exception()]
                    if exception:
                        raise cast(Exception, exception[0])

                for name, instance, log_level in services_started:
                    for registry in getattr(instance, "discovery", []):
                        registered_services.add(instance)
                        if getattr(registry, "_register_service", None):
                            await registry._register_service(instance)

                    started_futures.add(getattr(instance, "_started_service", None))
                    stop_futures.add(getattr(instance, "_stop_service", None))

                    self.logger.info('Started service "{}" [id: {}]'.format(name, instance.uuid))
            except Exception as e:
                self.logger.warning("Failed to start service")
                started_futures = set()
                self.stop_service()
                logging.getLogger("exception").exception("Uncaught exception: {}".format(str(e)))

            if started_futures and any(started_futures):
                await asyncio.wait([asyncio.ensure_future(func()) for func in started_futures if func])
        else:
            self.logger.warning("No transports defined in service file")
            self.stop_service()

        self.services_started = services_started
        if not self.started_waiter.done():
            self.started_waiter.set_result(services_started)

        await self.wait_stopped()
        for name, instance, log_level in services_started:
            self.logger.info('Stopping service "{}" [id: {}]'.format(name, instance.uuid))

        for instance in registered_services:
            for registry in getattr(instance, "discovery", []):
                if getattr(registry, "_deregister_service", None):
                    await registry._deregister_service(instance)

        if stop_futures and any(stop_futures):
            await asyncio.wait([asyncio.ensure_future(func()) for func in stop_futures if func])

        for name, instance, log_level in services_started:
            self.logger.info('Stopped service "{}" [id: {}]'.format(name, instance.uuid))

        # Debug output if TOMODACHI_DEBUG env is set. Shows still running tasks on service termination.
        if os.environ.get("TOMODACHI_DEBUG") and os.environ.get("TOMODACHI_DEBUG") != "0":
            try:
                tasks = [task for task in asyncio.all_tasks()]
                for task in tasks:
                    try:
                        co_filename = task.get_coro().cr_code.co_filename if hasattr(task, "get_coro") else task._coro.cr_code.co_filename  # type: ignore
                        co_name = task.get_coro().cr_code.co_name if hasattr(task, "get_coro") else task._coro.cr_code.co_name  # type: ignore

                        if "/tomodachi/watcher.py" in co_filename and co_name == "_watch_loop":
                            continue
                        if "/tomodachi/container.py" in co_filename and co_name == "run_until_complete":
                            continue
                        if "/asyncio/tasks.py" in co_filename and co_name == "wait":
                            continue

                        self.logger.warning(
                            "** Task '{}' from '{}' has not finished execution or has not been awaited".format(
                                co_name, co_filename
                            )
                        )
                    except Exception:
                        pass
            except Exception:
                pass

    @classmethod
    def assign_service_name(cls, instance: Any) -> str:
        new_service_name = ""
        if instance.__class__.__module__ and instance.__class__.__module__ not in (
            "service.app",
            "service.service",
            "services.app",
            "services.service",
            "src.service",
            "src.app",
            "code.service",
            "code.app",
            "app.service",
            "app.app",
            "apps.service",
            "apps.app",
            "example.service",
            "example.app",
            "examples.service",
            "examples.app",
            "test.service",
            "test.app",
            "tests.service",
            "tests.app",
        ):
            new_service_name = (
                "{}-".format(
                    re.sub(
                        r"^.*[.]([a-zA-Z0-9_]+)[.]([a-zA-Z0-9_]+)$",
                        r"\1-\2",
                        str(instance.__class__.__module__),
                    )
                )
                .replace("_", "-")
                .replace(".", "-")
            )
        class_name = instance.__class__.__name__
        for i, c in enumerate(class_name.lower()):
            if i and c != class_name[i]:
                new_service_name += "-"
            if c == "_":
                c = "-"
            new_service_name += c

        if new_service_name in ("app", "service"):
            new_service_name = "service"

        if not tomodachi.get_service(new_service_name) and not tomodachi.get_service(
            "{}-0001".format(new_service_name)
        ):
            service_name = new_service_name
        else:
            if tomodachi.get_service(new_service_name) and not tomodachi.get_service(
                "{}-0001".format(new_service_name)
            ):
                other_service = tomodachi.get_service(new_service_name)
                setattr(other_service, "name", "{}-0001".format(new_service_name))
                setattr(other_service.__class__, "name", other_service.name)
                unset_service(new_service_name)
                set_service(other_service.name, other_service)

            incr = 1
            while True:
                test_service_name = "{}-{:04d}".format(new_service_name, incr)
                if tomodachi.get_service(test_service_name):
                    incr += 1
                    continue
                service_name = test_service_name
                break

        setattr(instance, "name", service_name)
        setattr(instance.__class__, "name", service_name)

        return service_name
