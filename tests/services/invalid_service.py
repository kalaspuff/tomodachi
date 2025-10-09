# flake8: noqa
import tomodachi


@tomodachi.service
class InvalidService(tomodachi.Service):
    name = "test_invalid"

    error = error  # type: ignore
