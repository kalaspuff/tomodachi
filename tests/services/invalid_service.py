# flake8: noqa
import tomodachi


@tomodachi.service
class InvalidService(object):
    name = 'test_invalid'

    def syntax_error(self) -> error:  # type: ignore
        pass
