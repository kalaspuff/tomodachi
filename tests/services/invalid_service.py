# flake8: noqa
import tomodachi


@tomodachi.service
class InvalidService(tomodachi.Service):
    name = "test_invalid"

    def syntax_error(self) -> error:  # type: ignore
        pass
