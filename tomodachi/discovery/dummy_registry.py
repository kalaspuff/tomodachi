import logging
from typing import Any, Dict  # noqa


class DummyRegistry(object):
    http_endpoints = {}  # type: Dict

    @classmethod
    async def add_http_endpoint(cls, service: Any, host: str, port: int, method: str, pattern: str) -> None:
        cls.http_endpoints[service] = cls.http_endpoints.get(service, [])
        cls.http_endpoints[service].append((host, port, method, pattern))

    @classmethod
    async def _register_service(cls, service: Any) -> None:
        logging.getLogger('discovery.dummy_registry').info('Registering service "{}" [id: {}]'.format(service.name, service.uuid))
        for host, port, method, pattern in cls.http_endpoints.get(service, []):
            pass

    @classmethod
    async def _deregister_service(cls, service: Any) -> None:
        logging.getLogger('discovery.dummy_registry').info('Deregistering service "{}" [id: {}]'.format(service.name, service.uuid))
        for host, port, method, pattern in cls.http_endpoints.pop(service, []):
            pass
