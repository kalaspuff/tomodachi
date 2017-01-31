import asyncio
import sys
import signal
import logging


class ServiceLauncher(object):
    @classmethod
    def run_until_complete(cls, services):
        async def stop_services():
            if not cls._close_waiter.done():
                cls._close_waiter.set_result(None)
                for service in services:
                    service.stop_service()
            await cls._close_waiter

        def sigintHandler(*args):
            sys.stdout.write('\b\b\r')
            sys.stdout.flush()
            logging.getLogger('system').warn('Received <ctrl+c> interrupt [SIGINT]')

        def sigtermHandler(*args):
            logging.getLogger('system').warn('Received termination signal [SIGTERM]')

        loop = asyncio.get_event_loop()
        cls._close_waiter = asyncio.Future()

        for signame in ('SIGINT', 'SIGTERM'):
            loop.add_signal_handler(getattr(signal, signame), asyncio.ensure_future, stop_services())

        signal.siginterrupt(signal.SIGTERM, False)
        signal.siginterrupt(signal.SIGUSR1, False)
        signal.signal(signal.SIGINT, sigintHandler)
        signal.signal(signal.SIGTERM, sigtermHandler)

        try:
            loop.run_until_complete(asyncio.wait([asyncio.ensure_future(service.run_until_complete()) for service in services]))
        except:
            for signame in ('SIGINT', 'SIGTERM'):
                loop.remove_signal_handler(getattr(signal, signame))
            loop = asyncio.get_event_loop()
            loop.run_until_complete(stop_services())
            raise
        finally:
            loop.run_until_complete(stop_services())
