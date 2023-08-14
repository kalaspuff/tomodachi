from tomodachi.discovery import aws_sns_registration as aws_sns_registration
from tomodachi.discovery import dummy_registry as dummy_registry
from tomodachi.discovery.aws_sns_registration import AWSSNSRegistration as AWSSNSRegistration
from tomodachi.discovery.aws_sns_registration import AWSSNSRegistration as aws_sns
from tomodachi.discovery.aws_sns_registration import AWSSNSRegistration as awssns
from tomodachi.discovery.dummy_registry import DummyRegistry as DummyRegistry
from tomodachi.discovery.dummy_registry import DummyRegistry as dummy
from tomodachi.discovery.dummy_registry import DummyRegistry as example

__all__ = [
    "AWSSNSRegistration",
    "awssns",
    "aws_sns",
    "DummyRegistry",
    "dummy",
    "example",
    "aws_sns_registration",
    "dummy_registry",
]
