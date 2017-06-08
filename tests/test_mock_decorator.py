import asyncio
import functools
import importlib
import mock


def mock_decorator(*args, **kwargs):
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def test_without_mocked_function(monkeypatch, capsys):
    import services.mock_decorator_service
    importlib.reload(services.mock_decorator_service)

    service = services.mock_decorator_service.MockDecoratorService()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(service.test())
    assert service.function_tested is False


def test_mocked_function(monkeypatch, capsys):
    with mock.patch('tomodachi.transport.aws_sns_sqs.aws_sns_sqs', mock_decorator):
        import services.mock_decorator_service
        importlib.reload(services.mock_decorator_service)

        service = services.mock_decorator_service.MockDecoratorService()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(service.test())
        assert service.function_tested is True
