from typing import Any, Dict

from tomodachi import logging


# An example discovery class which would could be extended to register which
# the started service' HTTP endpoints are.
class DummyRegistry(object):
    http_endpoints: Dict = {}

    @classmethod
    async def add_http_endpoint(cls, service: Any, host: str, port: int, method: str, pattern: str) -> None:
        cls.http_endpoints[service] = cls.http_endpoints.get(service, [])
        cls.http_endpoints[service].append((host, port, method, pattern))

    @classmethod
    async def _register_service(cls, service: Any) -> None:
        logging.getLogger("tomodachi.discovery.example").info(
            "registering service endpoints", service_name=service.name, service_uuid=service.uuid
        )
        for host, port, method, pattern in cls.http_endpoints.get(service, []):
            pass

    @classmethod
    async def _deregister_service(cls, service: Any) -> None:
        logging.getLogger("tomodachi.discovery.example").info(
            "deregistering service", service_name=service.name, service_uuid=service.uuid
        )
        for host, port, method, pattern in cls.http_endpoints.pop(service, []):
            pass
