import inspect
import asyncio
import sys
import logging
import re
import traceback
import uuid
from tomodachi.invoker import FUNCTION_ATTRIBUTE


class ServiceContainer(object):
    def __init__(self, module_import):
        self.module_import = module_import
        self.module_name = module_import.__name__

        self.logger = logging.getLogger('services.{}'.format(self.module_name))
        self._close_waiter = asyncio.Future()

        def catch_uncaught_exceptions(exc_cls, exc, tb):
            raise exc

        sys.excepthook = catch_uncaught_exceptions

    def stop_service(self):
        if not self._close_waiter.done():
            self._close_waiter.set_result(None)

    async def wait_stopped(self):
        await self._close_waiter

    async def run_until_complete(self):
        services_started = set()
        invoker_tasks = set()
        start_futures = set()
        stop_futures = set()
        started_futures = set()
        registered_services = set()
        for _, cls in inspect.getmembers(self.module_import):
            if inspect.isclass(cls):
                instance = cls()
                instance.uuid = str(uuid.uuid1())

                # todo: fix function to get data from instance / class
                try:
                    service_name = cls.name
                except AttributeError:
                    _instance = cls()
                    try:
                        service_name = _instance.name
                    except AttributeError:
                        continue

                try:
                    log_level = cls.log_level
                except AttributeError:
                    _instance = cls()
                    try:
                        log_level = _instance.log_level
                    except AttributeError:
                        log_level = 'INFO'

                def invoker_function_sorter(m):
                    for i, line in enumerate(inspect.getsourcelines(self.module_import)[0]):
                        if re.match(r'^\s*(async)?\s+def\s+{}\s*([(].*$)?$'.format(m), line):
                            return i
                    return -1

                invoker_functions = [name for name, fn in inspect.getmembers(cls) if inspect.isfunction(fn) and getattr(fn, FUNCTION_ATTRIBUTE, None)]
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
                    started_futures.add(getattr(instance, '_started_service'))
                    services_started.add((service_name, instance, log_level))
                except AttributeError:
                    pass

        if services_started:
            try:
                for name, instance, log_level in services_started:
                    self.logger.info('Initializing service "{}" [id: {}]'.format(name, instance.uuid))

                if invoker_tasks:
                    task_results = await asyncio.wait([asyncio.ensure_future(func()) for func in (await asyncio.gather(*invoker_tasks)) if func])
                    exception = [list(v)[0].exception() for v in [value for value in task_results if value] if list(v)[0].exception()]
                    if exception:
                        raise exception[0]
                if start_futures:
                    await asyncio.wait([asyncio.ensure_future(func()) for func in start_futures if func])

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
                        stop_futures.add(getattr(instance, '_stop_service'))
                    except AttributeError:
                        pass

                    self.logger.info('Started service "{}" [id: {}]'.format(name, instance.uuid))
            except Exception as e:
                self.logger.warn('Failed to start service')
                started_futures = None
                self.stop_service()
                try:
                    if not getattr(e, '_log_level') or e._log_level in ['DEBUG']:
                        traceback.print_exception(e.__class__, e, e.__traceback__)
                except AttributeError:
                    traceback.print_exception(e.__class__, e, e.__traceback__)

            if started_futures:
                await asyncio.wait([asyncio.ensure_future(func()) for func in started_futures if func])
        else:
            self.logger.warn('No transports defined in service file')
            self.stop_service()

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
