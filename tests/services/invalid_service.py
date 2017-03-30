# flake8: noqa
import tomodachi


@tomodachi.service
class InvalidService(object):
    name = 'test_invalid'

    def syntax_error{}:  # noqa: E901
        pass
