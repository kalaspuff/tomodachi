import logging
import signal
import functools
import asyncio
from tomodachi.container import ServiceContainer
from tomodachi.importer import ServiceImporter


def start_service(filename, monkeypatch=None):
    if monkeypatch:
        monkeypatch.setattr(logging.root, 'handlers', [])

    loop = asyncio.get_event_loop()
    service = None

    def stop_services(loop=None):
        if not loop:
            loop = asyncio.get_event_loop()
        asyncio.wait([asyncio.ensure_future(_stop_services())])

    async def _stop_services():
        service.stop_service()

    for signame in ('SIGINT', 'SIGTERM'):
        loop.add_signal_handler(getattr(signal, signame), functools.partial(stop_services, loop))

    try:
        service = ServiceContainer(ServiceImporter.import_service_file(filename))
        assert service is not None
        async def _async():
            loop = asyncio.get_event_loop()
            try:
                await service.run_until_complete()
            except:
                loop = asyncio.get_event_loop()
                stop_services(loop)
                raise

        future = asyncio.ensure_future(_async())
        loop.run_until_complete(asyncio.wait([service.started_waiter]))
    except:
        for signame in ('SIGINT', 'SIGTERM'):
            loop.remove_signal_handler(getattr(signal, signame))
        loop = asyncio.get_event_loop()
        stop_services(loop)
        raise

    services = {}
    for service_name, instance, log_level in service.started_waiter.result():
        services[service_name] = instance

    return services, future
