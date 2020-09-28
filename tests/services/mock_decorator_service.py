import tomodachi
from tomodachi.transport.aws_sns_sqs import aws_sns_sqs


@tomodachi.service
class MockDecoratorService(tomodachi.Service):
    name = "mock_decorator"
    log_level = "INFO"
    function_tested = False

    @aws_sns_sqs("test-topic")
    async def test(self, default_value: bool = True) -> None:
        self.function_tested = default_value
