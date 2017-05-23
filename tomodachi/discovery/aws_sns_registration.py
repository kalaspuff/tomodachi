import logging
from tomodachi.transport.aws_sns_sqs import aws_sns_sqs_publish


class AWSSNSRegistration(object):
    http_endpoints = {}

    @classmethod
    async def add_http_endpoint(cls, service, host, port, method, pattern):
        cls.http_endpoints[service] = cls.http_endpoints.get(service, [])
        cls.http_endpoints[service].append((host, port, method, pattern))

    @classmethod
    async def _register_service(cls, service):
        logging.getLogger('discovery.aws_sns_registration').info('Registering service "{}" [id: {}]'.format(service.name, service.uuid))
        data = {
            'name': service.name,
            'uuid': service.uuid,
            'http_endpoints': cls.http_endpoints.get(service)
        }
        await aws_sns_sqs_publish(service, data, topic='services.registration.register')

    @classmethod
    async def _deregister_service(cls, service):
        logging.getLogger('discovery.aws_sns_registration').info('Deregistering service "{}" [id: {}]'.format(service.name, service.uuid))
        data = {
            'name': service.name,
            'uuid': service.uuid
        }
        try:
            await aws_sns_sqs_publish(service, data, topic='services.registration.deregister')
        except:
            logging.getLogger('discovery.aws_sns_registration').info('Deregistering service "{}" failed [id: {}]'.format(service.name, service.uuid))
