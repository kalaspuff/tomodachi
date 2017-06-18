import inspect
import asyncio
import sys
import logging
import re
import traceback
import types
import uuid
from types import ModuleType, TracebackType
from typing import Dict, Optional, Any, Type
from tomodachi import CLASS_ATTRIBUTE
from tomodachi.invoker import FUNCTION_ATTRIBUTE, START_ATTRIBUTE
from tomodachi.config import merge_dicts


class ServiceContainer(object):
    def __init__(self, module_import: ModuleType, configuration: Optional[Dict]=None) -> None:
        self.module_import = module_import
        try:
            self.module_name = module_import.__name__.rsplit('/', 1)[1]
        except IndexError:
            self.module_name = module_import.__name__

        self.configuration = configuration

        self.logger = logging.getLogger('services.{}'.format(self.module_name))

        self._close_waiter = asyncio.Future()  # type: asyncio.Future
        self.started_waiter = asyncio.Future()  # type: asyncio.Future

        def catch_uncaught_exceptions(type_: Type[BaseException], value: BaseException, traceback: TracebackType) -> None:
            raise value

        sys.excepthook = catch_uncaught_exceptions

    def stop_service(self) -> None:
        if not self._close_waiter.done():
            self._close_waiter.set_result(None)

    def setup_configuration(self, instance: Any) -> None:
        if not self.configuration:
            return
        for k, v in self.configuration.items():
            try:
                instance_value = getattr(instance, k)
            except AttributeError:
                instance_value = None
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

                self.setup_configuration(instance)

                try:
                    if not instance.uuid:
                        instance.uuid = str(uuid.uuid4())
                except AttributeError:
                    instance.uuid = str(uuid.uuid4())

                try:
                    service_name = instance.name
                except AttributeError:
                    try:
                        service_name = cls.name
                    except AttributeError:
                        continue

                try:
                    log_level = instance.log_level
                except AttributeError:
                    try:
                        log_level = cls.log_level
                    except AttributeError:
                        log_level = 'INFO'

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

                try:
                    getattr(instance, '_started_service')
                    services_started.add((service_name, instance, log_level))
                except AttributeError:
                    pass

        if services_started:
            try:
                for name, instance, log_level in services_started:
                    self.logger.info('Initializing service "{}" [id: {}]'.format(name, instance.uuid))

                if invoker_tasks:
                    task_results = await asyncio.wait([asyncio.ensure_future(func()) for func in (await asyncio.gather(*invoker_tasks)) if func])
                    exception = [v.exception() for v in [value for value in task_results if value][0] if v.exception()]
                    if exception:
                        raise exception[0]
                if start_futures:
                    start_task_results = await asyncio.wait([asyncio.ensure_future(func()) for func in start_futures if func])
                    exception = [v.exception() for v in [value for value in start_task_results if value][0] if v.exception()]
                    if exception:
                        raise exception[0]

                for name, instance, log_level in services_started:
                    try:
                        for registry in instance.discovery:
                            registered_services.add(instance)
                            try:
                                if getattr(registry, '_register_service'):
                                    await registry._register_service(instance)
                            except AttributeError:
                                pass
                    except AttributeError:
                        pass

                    try:
                        started_futures.add(getattr(instance, '_started_service'))
                    except AttributeError:
                        pass

                    try:
                        stop_futures.add(getattr(instance, '_stop_service'))
                    except AttributeError:
                        pass

                    self.logger.info('Started service "{}" [id: {}]'.format(name, instance.uuid))
            except Exception as e:
                self.logger.warning('Failed to start service')
                started_futures = set()
                self.stop_service()
                try:
                    if not getattr(e, '_log_level') or getattr(e, '_log_level') in ['DEBUG']:
                        traceback.print_exception(e.__class__, e, e.__traceback__)
                except AttributeError:
                    traceback.print_exception(e.__class__, e, e.__traceback__)

            if started_futures:
                await asyncio.wait([asyncio.ensure_future(func()) for func in started_futures if func])
        else:
            self.logger.warning('No transports defined in service file')
            self.stop_service()

        self.services_started = services_started
        self.started_waiter.set_result(services_started)

        await self.wait_stopped()
        for name, instance, log_level in services_started:
            self.logger.info('Stopping service "{}" [id: {}]'.format(name, instance.uuid))

        for instance in registered_services:
            try:
                for registry in instance.discovery:
                    try:
                        if getattr(registry, '_deregister_service'):
                            await registry._deregister_service(instance)
                    except AttributeError:
                        pass
            except AttributeError:
                pass

        if stop_futures:
            await asyncio.wait([asyncio.ensure_future(func()) for func in stop_futures if func])
        for name, instance, log_level in services_started:
            self.logger.info('Stopped service "{}" [id: {}]'.format(name, instance.uuid))
