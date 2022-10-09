import asyncio
import functools
import logging
import signal
import sys
from typing import Any, Dict, Optional, Tuple

from tomodachi.container import ServiceContainer
from tomodachi.importer import ServiceImporter
from tomodachi.launcher import ServiceLauncher


def start_service(filename: str, monkeypatch: Any = None, wait: bool = True, loop: Optional[asyncio.AbstractEventLoop] = None) -> Tuple:
    if not loop:
        if sys.version_info.major == 3 and sys.version_info.minor < 10:
            loop = asyncio.get_event_loop()
        else:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

    async def _async() -> Tuple:
        return await _start_service(filename, monkeypatch, wait=wait, loop=asyncio.get_event_loop())

    return loop.run_until_complete(_async())

async def _start_service(filename: str, monkeypatch: Any = None, wait: bool = True, loop: Optional[asyncio.AbstractEventLoop] = None) -> Tuple:
    if monkeypatch:
        monkeypatch.setattr(logging.root, "handlers", [])

    if not loop:
        raise Exception("loop missing")

    service: Optional[ServiceContainer] = None

    def stop_services(loop: Any = None) -> None:
        ServiceLauncher.stop_services_post_hook = None
        if not loop:
            loop = asyncio.get_event_loop()
        asyncio.ensure_future(_stop_services())

    def force_stop_services(loop: Any = None) -> None:
        ServiceLauncher.stop_services_post_hook = None
        if not loop:
            loop = asyncio.get_event_loop()
        asyncio.ensure_future(_force_stop_services())

    async def _stop_services() -> None:
        if service:
            service.stop_service()

    async def _force_stop_services() -> None:
        if service and not service.started_waiter:
            service.started_waiter = asyncio.Future()
        if service and not service.started_waiter.done():
            service.started_waiter.set_result([])

    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), functools.partial(stop_services, loop))

    ServiceLauncher.stop_services_post_hook = _stop_services

    try:
        service = ServiceContainer(ServiceImporter.import_service_file(filename))
        assert service is not None

        async def _async() -> None:
            loop = asyncio.get_event_loop()
            try:
                await service.run_until_complete()
            except Exception:
                loop = asyncio.get_event_loop()
                stop_services(loop)
                force_stop_services(loop)
                raise

        future = asyncio.ensure_future(_async())
        if service and not service.started_waiter:
            service.started_waiter = asyncio.Future()
        if wait:
            await asyncio.wait([service.started_waiter])
    except Exception:
        for signame in ("SIGINT", "SIGTERM"):
            loop.remove_signal_handler(getattr(signal, signame))
        loop = asyncio.get_event_loop()
        for signame in ("SIGINT", "SIGTERM"):
            loop.remove_signal_handler(getattr(signal, signame))
        if service:
            stop_services(loop)
        raise

    services = {}
    if wait:
        for service_name, instance, log_level in service.started_waiter.result():
            services[service_name] = instance
    else:

        async def get_services() -> Dict:
            await asyncio.wait([service.started_waiter])
            return {service_name: instance for service_name, instance, log_level in service.started_waiter.result()}

        return get_services, future

    return services, future
