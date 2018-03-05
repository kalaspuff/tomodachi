import asyncio
import sys
import signal
import importlib
import logging
import datetime
import uvloop
import traceback
import os
import multidict  # noqa
import yarl  # noqa
from typing import Dict, Union, Optional, Any, List
import tomodachi.container
import tomodachi.importer
import tomodachi.invoker
import tomodachi.__version__
import tomodachi.watcher
from tomodachi.container import ServiceContainer
from tomodachi.importer import ServiceImporter


class ServiceLauncher(object):
    _close_waiter = None  # type: Union[None, asyncio.Future]
    _stopped_waiter = None  # type: Union[None, asyncio.Future]
    restart_services = False
    services = set()  # type: set

    @classmethod
    def run_until_complete(cls, service_files: Union[List, set], configuration: Optional[Dict]=None, watcher: Optional[tomodachi.watcher.Watcher]=None) -> None:
        def stop_services() -> None:
            asyncio.wait([asyncio.ensure_future(_stop_services())])

        async def _stop_services() -> None:
            if cls._close_waiter and not cls._close_waiter.done():
                cls._close_waiter.set_result(None)
                for service in cls.services:
                    try:
                        service.stop_service()
                    except Exception:
                        pass
                if cls._stopped_waiter:
                    cls._stopped_waiter.set_result(None)
            if cls._stopped_waiter:
                await cls._stopped_waiter

        def sigintHandler(*args: Any) -> None:
            sys.stdout.write('\b\b\r')
            sys.stdout.flush()
            logging.getLogger('system').warning('Received <ctrl+c> interrupt [SIGINT]')
            cls.restart_services = False

        def sigtermHandler(*args: Any) -> None:
            logging.getLogger('system').warning('Received termination signal [SIGTERM]')
            cls.restart_services = False

        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        loop = asyncio.get_event_loop()

        for signame in ('SIGINT', 'SIGTERM'):
            loop.add_signal_handler(getattr(signal, signame), stop_services)

        signal.siginterrupt(signal.SIGTERM, False)
        signal.siginterrupt(signal.SIGUSR1, False)
        signal.signal(signal.SIGINT, sigintHandler)
        signal.signal(signal.SIGTERM, sigtermHandler)

        if watcher:
            async def _watcher_restart(updated_files: Union[List, set]) -> None:
                cls.restart_services = True

                for file in service_files:
                    try:
                        ServiceImporter.import_service_file(file)
                    except (SyntaxError, IndentationError) as e:
                        traceback.print_exception(e.__class__, e, e.__traceback__)
                        logging.getLogger('watcher.restart').warning('Service cannot restart due to errors')
                        cls.restart_services = False
                        return

                pre_import_current_modules = [m for m in sys.modules.keys()]
                cwd = os.getcwd()
                for file in updated_files:
                    if file.lower().endswith('.py'):
                        module_name = file[:-3].replace('/', '.')
                        module_name_full_path = '{}/{}'.format(os.path.realpath(cwd), file)[:-3].replace('/', '.')
                        try:
                            for m in pre_import_current_modules:
                                if m == module_name or (len(m) > len(file) and module_name_full_path.endswith(m)):
                                    ServiceImporter.import_module(file)
                        except (SyntaxError, IndentationError) as e:
                            traceback.print_exception(e.__class__, e, e.__traceback__)
                            logging.getLogger('watcher.restart').warning('Service cannot restart due to errors')
                            cls.restart_services = False
                            return

                logging.getLogger('watcher.restart').warning('Restarting services')
                stop_services()

            watcher_future = loop.run_until_complete(watcher.watch(loop=loop, callback_func=_watcher_restart))

        cls.restart_services = True
        init_modules = [m for m in sys.modules.keys()]
        safe_modules = ['typing', 'importlib.util', 'time', 'logging', 're', 'traceback', 'types', 'inspect', 'functools']

        restarting = False
        while cls.restart_services:
            if watcher:
                print('---')
                print('Starting services...')
                print()
                print('tomodachi/{}'.format(tomodachi.__version__))
                print(datetime.datetime.now().strftime('%B %d, %Y - %H:%M:%S,%f'))
                print('Quit services with <ctrl+c>.')

            cls._close_waiter = asyncio.Future()
            cls._stopped_waiter = asyncio.Future()
            cls.restart_services = False

            try:
                cls.services = set([ServiceContainer(ServiceImporter.import_service_file(file), configuration) for file in service_files])
                result = loop.run_until_complete(asyncio.wait([asyncio.ensure_future(service.run_until_complete()) for service in cls.services]))
                exception = [v.exception() for v in [value for value in result if value][0] if v.exception()]
                if exception:
                    raise exception[0]
            except Exception as e:
                traceback.print_exception(e.__class__, e, e.__traceback__)
                if restarting:
                    logging.getLogger('watcher.restart').warning('Service cannot restart due to errors')
                    logging.getLogger('watcher.restart').warning('Trying again in 1.5 seconds')
                    loop.run_until_complete(asyncio.wait([asyncio.sleep(1.5)]))
                    if cls._close_waiter and not cls._close_waiter.done():
                        cls.restart_services = True
                    else:
                        for signame in ('SIGINT', 'SIGTERM'):
                            loop.remove_signal_handler(getattr(signal, signame))
                else:
                    for signame in ('SIGINT', 'SIGTERM'):
                        loop.remove_signal_handler(getattr(signal, signame))

            current_modules = [m for m in sys.modules.keys()]
            for m in current_modules:
                if m not in init_modules and m not in safe_modules:
                    del(sys.modules[m])

            importlib.reload(tomodachi.container)
            importlib.reload(tomodachi.invoker)
            importlib.reload(tomodachi.invoker.base)
            importlib.reload(tomodachi.importer)

            restarting = True

        if watcher:
            if not watcher_future.done():
                watcher_future.set_result(None)
                if not watcher_future.done():
                    loop.run_until_complete(watcher_future)
