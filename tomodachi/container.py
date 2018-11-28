import inspect
import asyncio
import sys
import logging
import re
import types
import uuid
import tomodachi
from types import ModuleType, TracebackType
from typing import Dict, Optional, Any
from tomodachi import CLASS_ATTRIBUTE
from tomodachi.invoker import FUNCTION_ATTRIBUTE, START_ATTRIBUTE
from tomodachi.config import merge_dicts


class ServiceContainer(object):
    def __init__(self, module_import: ModuleType, configuration: Optional[Dict] = None) -> None:
        self.module_import = module_import

        self.file_path = module_import.__file__
        self.module_name = (module_import.__name__.rsplit('/', 1)[1] if '/' in module_import.__name__ else module_import.__name__).rsplit('.', 1)[-1]
        self.configuration = configuration
        self.logger = logging.getLogger('services.{}'.format(self.module_name))

        self._close_waiter = asyncio.Future()  # type: asyncio.Future
        self.started_waiter = asyncio.Future()  # type: asyncio.Future

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
        services_started = set()  # type: set
        invoker_tasks = set()  # type: set
        start_futures = set()  # type: set
        stop_futures = set()  # type: set
        started_futures = set()  # type: set
        registered_services = set()  # type: set
        for _, cls in inspect.getmembers(self.module_import):
            if inspect.isclass(cls):
                if not getattr(cls, CLASS_ATTRIBUTE, None):
                    continue

                instance = cls()
                if not getattr(instance, 'context', None):
                    setattr(instance, 'context', {i: getattr(instance, i) for i in dir(instance) if not callable(i) and not i.startswith("__") and not isinstance(getattr(instance, i), types.MethodType)})

                getattr(instance, 'context', {})['_service_file_path'] = self.file_path

                self.setup_configuration(instance)

                if not getattr(instance, 'uuid', None):
                    instance.uuid = str(uuid.uuid4())

                service_name = getattr(instance, 'name', getattr(cls, 'name', None))
                if not service_name:
                    continue

                tomodachi.set_service(service_name, instance)

                log_level = getattr(instance, 'log_level', None) or getattr(cls, 'log_level', None) or 'INFO'

                def invoker_function_sorter(m: str) -> int:
                    for i, line in enumerate(inspect.getsourcelines(self.module_import)[0]):
                        if re.match(r'^\s*(async)?\s+def\s+{}\s*([(].*$)?$'.format(m), line):
                            return i
                    return -1

                invoker_functions = []
                for name, fn in inspect.getmembers(cls):
                    if inspect.isfunction(fn) and getattr(fn, FUNCTION_ATTRIBUTE, None):
                        setattr(fn, START_ATTRIBUTE, True)
                        invoker_functions.append(name)
                invoker_functions.sort(key=invoker_function_sorter)
                if invoker_functions:
                    invoker_tasks = invoker_tasks | set([asyncio.ensure_future(getattr(instance, name)()) for name in invoker_functions])
                    services_started.add((service_name, instance, log_level))

                try:
                    start_futures.add(getattr(instance, '_start_service'))
                    services_started.add((service_name, instance, log_level))
                except AttributeError:
                    pass

                if getattr(instance, '_started_service', None):
                    services_started.add((service_name, instance, log_level))

        if services_started:
            try:
                for name, instance, log_level in services_started:
                    self.logger.info('Initializing service "{}" [id: {}]'.format(name, instance.uuid))

                if start_futures:
                    start_task_results = await asyncio.wait([asyncio.ensure_future(func()) for func in start_futures if func])
                    exception = [v.exception() for v in [value for value in start_task_results if value][0] if v.exception()]
                    if exception:
                        raise exception[0]
                if invoker_tasks:
                    task_results = await asyncio.wait([asyncio.ensure_future(func()) for func in (await asyncio.gather(*invoker_tasks)) if func])
                    exception = [v.exception() for v in [value for value in task_results if value][0] if v.exception()]
                    if exception:
                        raise exception[0]

                for name, instance, log_level in services_started:
                    for registry in getattr(instance, 'discovery', []):
                        registered_services.add(instance)
                        if getattr(registry, '_register_service', None):
                            await registry._register_service(instance)

                    started_futures.add(getattr(instance, '_started_service', None))
                    stop_futures.add(getattr(instance, '_stop_service', None))

                    self.logger.info('Started service "{}" [id: {}]'.format(name, instance.uuid))
            except Exception as e:
                self.logger.warning('Failed to start service')
                started_futures = set()
                self.stop_service()
                logging.getLogger('exception').exception('Uncaught exception: {}'.format(str(e)))

            if started_futures and any(started_futures):
                await asyncio.wait([asyncio.ensure_future(func()) for func in started_futures if func])
        else:
            self.logger.warning('No transports defined in service file')
            self.stop_service()

        self.services_started = services_started
        if not self.started_waiter.done():
            self.started_waiter.set_result(services_started)

        await self.wait_stopped()
        for name, instance, log_level in services_started:
            self.logger.info('Stopping service "{}" [id: {}]'.format(name, instance.uuid))

        for instance in registered_services:
            for registry in getattr(instance, 'discovery', []):
                if getattr(registry, '_deregister_service', None):
                    await registry._deregister_service(instance)

        if stop_futures and any(stop_futures):
            await asyncio.wait([asyncio.ensure_future(func()) for func in stop_futures if func])
        for name, instance, log_level in services_started:
            self.logger.info('Stopped service "{}" [id: {}]'.format(name, instance.uuid))
