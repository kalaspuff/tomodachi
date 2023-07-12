from typing import Any, Dict

from tomodachi import logging
from tomodachi.transport.aws_sns_sqs import aws_sns_sqs_publish


# An example discovery class which would send a message over AWS SNS on the topic
# 'services-registration-register' containing the newly started service-name and
# the HTTP endpoitns that it's listening on. Likewise it also tries to "deregister"
# by sending a message on the 'services-registration-deregister' when shutting
# down.
class AWSSNSRegistration(object):
    name: str = "tomodachi.discovery.awssns"
    http_endpoints: Dict = {}

    @classmethod
    async def add_http_endpoint(cls, service: Any, host: str, port: int, method: str, pattern: str) -> None:
        cls.http_endpoints[service] = cls.http_endpoints.get(service, [])
        cls.http_endpoints[service].append((host, port, method, pattern))

    @classmethod
    async def _register_service(cls, service: Any) -> None:
        logging.getLogger().info("registering service endpoints")
        data = {"name": service.name, "uuid": service.uuid, "http_endpoints": cls.http_endpoints.get(service)}
        await aws_sns_sqs_publish(service, data, topic="services-registration-register")

    @classmethod
    async def _deregister_service(cls, service: Any) -> None:
        logger = logging.getLogger()
        logger.info("deregistering service")
        data = {"name": service.name, "uuid": service.uuid}
        try:
            await aws_sns_sqs_publish(service, data, topic="services-registration-deregister")
        except Exception as e:
            logger.warning("deregistering failed", error=str(e))
