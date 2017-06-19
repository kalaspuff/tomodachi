import asyncio
import services.mock_decorator_service


def test_without_mocked_invoker_function() -> None:
    service = services.mock_decorator_service.MockDecoratorService()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(service.test())
    assert service.function_tested is True
