import re


class RegexMissmatchException(Exception):
    def __init__(self, value: str, pattern: str):
        message = f'RegexMissmatchException: value "{value}" does not match pattern "{pattern}"'
        super().__init__(message)


def validate_field_regex(value: str, pattern_str: str):
    pattern = re.compile(pattern_str)
    if not pattern.match(value):
        raise RegexMissmatchException(value=value, pattern=pattern_str)
