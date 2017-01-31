import logging


class Registry(object):
    http_endpoints = {}

    @classmethod
    async def add_http_endpoint(cls, service, host, port, method, pattern):
        cls.http_endpoints[service] = cls.http_endpoints.get(service, [])
        cls.http_endpoints[service].append((host, port, method, pattern))

    @classmethod
    async def _register_service(cls, service):
        logging.getLogger('discovery.registry').info('Registering service "{}" [id: {}]'.format(service.name, service.uuid))
        for host, port, method, pattern in cls.http_endpoints.get(service, []):
            pass

    @classmethod
    async def _deregister_service(cls, service):
        logging.getLogger('discovery.registry').info('Deregistering service "{}" [id: {}]'.format(service.name, service.uuid))
        for host, port, method, pattern in cls.http_endpoints.pop(service, []):
            pass
