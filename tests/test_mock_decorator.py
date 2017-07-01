from typing import Any
import services.mock_decorator_service


def test_without_mocked_invoker_function(loop: Any) -> None:
    service = services.mock_decorator_service.MockDecoratorService()

    loop.run_until_complete(service.test())
    assert service.function_tested is True
