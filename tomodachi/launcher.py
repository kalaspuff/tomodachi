import asyncio
import sys
import signal
import importlib
import logging
import functools
import datetime
import uvloop
import tomodachi.container
import tomodachi.importer
import tomodachi.invoker
import tomodachi.__version__
from tomodachi.container import ServiceContainer
from tomodachi.importer import ServiceImporter


class ServiceLauncher(object):
    _close_waiter = None
    _stopped_waiter = None
    restart_services = False
    services = None

    @classmethod
    def run_until_complete(cls, service_files, configuration=None, watcher=None):
        def stop_services(loop=None):
            asyncio.wait([asyncio.ensure_future(_stop_services())])

        async def _stop_services():
            if not cls._close_waiter.done():
                cls._close_waiter.set_result(None)
                for service in cls.services:
                    service.stop_service()
                cls._stopped_waiter.set_result(None)
            await cls._stopped_waiter

        def sigintHandler(*args):
            sys.stdout.write('\b\b\r')
            sys.stdout.flush()
            logging.getLogger('system').warning('Received <ctrl+c> interrupt [SIGINT]')

        def sigtermHandler(*args):
            logging.getLogger('system').warning('Received termination signal [SIGTERM]')

        if not isinstance(service_files, list) and not isinstance(service_files, set):
            service_files = [service_files]

        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        loop = asyncio.get_event_loop()

        for signame in ('SIGINT', 'SIGTERM'):
            loop.add_signal_handler(getattr(signal, signame), functools.partial(stop_services, loop))

        signal.siginterrupt(signal.SIGTERM, False)
        signal.siginterrupt(signal.SIGUSR1, False)
        signal.signal(signal.SIGINT, sigintHandler)
        signal.signal(signal.SIGTERM, sigtermHandler)

        if watcher:
            async def _watcher_restart():
                cls.restart_services = True
                logging.getLogger('watcher.restart').warning('Restarting services')
                stop_services(loop)

            watcher_future = loop.run_until_complete(watcher.watch(loop=loop, callback_func=_watcher_restart))

        cls.restart_services = True
        init_modules = [m for m in sys.modules.keys()]
        safe_modules = ['typing', 'importlib.util', 'time', 'logging', 're', 'traceback', 'types', 'inspect']

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
                loop.run_until_complete(asyncio.wait([asyncio.ensure_future(service.run_until_complete()) for service in cls.services]))
            except:
                for signame in ('SIGINT', 'SIGTERM'):
                    loop.remove_signal_handler(getattr(signal, signame))
                loop = asyncio.get_event_loop()
                stop_services(loop)
                raise

            current_modules = [m for m in sys.modules.keys()]
            for m in current_modules:
                if m not in init_modules and m not in safe_modules:
                    del(sys.modules[m])

            importlib.reload(tomodachi.container)
            importlib.reload(tomodachi.invoker)
            importlib.reload(tomodachi.invoker.base)
            importlib.reload(tomodachi.importer)

        if watcher:
            if not watcher_future.done():
                watcher_future.set_result(None)
                if not watcher_future.done():
                    loop.run_until_complete(watcher_future)
