# flake8: noqa
class InvalidService(object):
    name = 'test_invalid'

    def syntax_error{}:  # noqa: E901
        pass
