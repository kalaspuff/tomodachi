import re
from typing import List, Union


class RegexMissmatchException(Exception):
    def __init__(self, value: str, pattern: str) -> None:
        message = 'RegexMissmatchException: value "{}" does not match pattern "{}"'.format(value, pattern)
        super().__init__(message)


class TooSmallException(Exception):
    def __init__(self, obj: Union[List, str], min_length: int) -> None:
        message = 'TooSmallException: "{}" is not at least of length {}'.format(obj, min_length)
        super().__init__(message)


class TooLargeException(Exception):
    def __init__(self, obj: Union[List, str], max_length: int) -> None:
        message = 'TooLargeException: "{}" length is larger than {}'.format(obj, max_length)
        super().__init__(message)


def validate_field_regex(value: str, pattern_str: str) -> None:
    pattern = re.compile(pattern_str)
    if not pattern.match(value):
        raise RegexMissmatchException(value=value, pattern=pattern_str)


def validate_field_length(obj: Union[List, str], min_length: int = -1, max_length: int = -1) -> None:
    if min_length != -1:
        if len(obj) < min_length:
            raise TooSmallException(obj=obj, min_length=min_length)
    if max_length != -1:
        if len(obj) > max_length:
            raise TooLargeException(obj=obj, max_length=max_length)
