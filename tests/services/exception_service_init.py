import tomodachi


@tomodachi.service
class ExceptionService(tomodachi.Service):
    name = "test_exception"
    log_level = "DEBUG"

    def __init__(self) -> None:
        raise Exception("fail in __init__()")

    async def _start_service(self) -> None:
        raise Exception("fail in _start_service()")
