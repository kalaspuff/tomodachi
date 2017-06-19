import tomodachi
from tomodachi.transport.aws_sns_sqs import aws_sns_sqs


@tomodachi.service
class MockDecoratorService(object):
    name = 'mock_decorator'
    log_level = 'INFO'
    function_tested = False

    @aws_sns_sqs('test-topic')
    async def test(self) -> None:
        self.function_tested = True
