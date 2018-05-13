import re


class RegexMissmatchException(Exception):
    def __init__(self, value: str, pattern: str) -> None:
        message = 'RegexMissmatchException: value "{}" does not match pattern "{}"'.format(value, pattern)
        super().__init__(message)


def validate_field_regex(value: str, pattern_str: str) -> None:
    pattern = re.compile(pattern_str)
    if not pattern.match(value):
        raise RegexMissmatchException(value=value, pattern=pattern_str)
