import logging
import signal
import functools
import asyncio
from typing import Any, Tuple
from tomodachi.container import ServiceContainer
from tomodachi.importer import ServiceImporter


def start_service(filename: str, monkeypatch: Any = None, wait: bool = True) -> Tuple:
    if monkeypatch:
        monkeypatch.setattr(logging.root, 'handlers', [])

    loop = asyncio.get_event_loop()  # type: Any
    service = None  # type: Any

    def stop_services(loop: Any = None) -> None:
        if not loop:
            loop = asyncio.get_event_loop()
        asyncio.ensure_future(_stop_services())

    def force_stop_services(loop: Any = None) -> None:
        if not loop:
            loop = asyncio.get_event_loop()
        asyncio.ensure_future(_force_stop_services())

    async def _stop_services() -> None:
        service.stop_service()

    async def _force_stop_services() -> None:
        if not service.started_waiter.done():
            service.started_waiter.set_result([])

    for signame in ('SIGINT', 'SIGTERM'):
        loop.add_signal_handler(getattr(signal, signame), functools.partial(stop_services, loop))

    try:
        service = ServiceContainer(ServiceImporter.import_service_file(filename))
        assert service is not None

        async def _async() -> None:
            loop = asyncio.get_event_loop()  # type: Any
            try:
                await service.run_until_complete()
            except Exception:
                loop = asyncio.get_event_loop()
                stop_services(loop)
                force_stop_services(loop)
                raise

        future = asyncio.ensure_future(_async())
        if wait:
            loop.run_until_complete(asyncio.wait([service.started_waiter]))
    except Exception:
        for signame in ('SIGINT', 'SIGTERM'):
            loop.remove_signal_handler(getattr(signal, signame))
        loop = asyncio.get_event_loop()
        if service:
            stop_services(loop)
        raise

    services = {}
    if wait:
        for service_name, instance, log_level in service.started_waiter.result():
            services[service_name] = instance
    else:
        def get_services():
            loop.run_until_complete(asyncio.wait([service.started_waiter]))
            return {service_name: instance for service_name, instance, log_level in service.started_waiter.result()}

        return get_services, future

    return services, future
