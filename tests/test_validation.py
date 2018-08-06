import pytest

from tomodachi.validation.validation import validate_field_regex, \
    RegexMissmatchException
from tomodachi.validation.validation import validate_field_length, \
    TooSmallException, TooLargeException


def test_regex_success() -> None:
    validate_field_regex('af047ca5-e8f4-48a9-ab01-1d948f635f95', r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


def test_regex_failure() -> None:
    with pytest.raises(RegexMissmatchException):
        validate_field_regex('a94a8fe5ccb19ba61c4c0873d391e987982fbbd3', r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


def test_string_length_success_1() -> None:
    validate_field_length('19840801', 6, 8)


def test_string_length_success_2() -> None:
    validate_field_length('840801', 6, 8)


def test_string_length_success_3() -> None:
    validate_field_length('a94a8fe5ccb19ba61c4c0873d391e987982fbbd3')


def test_string_length_success_4() -> None:
    validate_field_length('')


def test_string_length_too_large() -> None:
    with pytest.raises(TooLargeException):
        validate_field_length('1984-08-01', 6, 8)


def test_string_length_too_small() -> None:
    with pytest.raises(TooSmallException):
        validate_field_length('8481', 6, 8)


def test_string_length_empty() -> None:
    with pytest.raises(TooSmallException):
        validate_field_length('', 1)


def test_list_length_success_1() -> None:
    validate_field_length(['a', 'b', 'c', 'd', 'e'], 2, 5)


def test_list_length_success_2() -> None:
    validate_field_length(['a', 'b'], 2, 5)


def test_list_length_success_3() -> None:
    validate_field_length([])


def test_list_length_success_4() -> None:
    validate_field_length(['a', 'b', 'c', 'd', 'e', 'f'])


def test_list_length_too_large() -> None:
    with pytest.raises(TooLargeException):
        validate_field_length(['a', 'b', 'c', 'd', 'e', 'f'], 2, 5)


def test_list_length_too_small() -> None:
    with pytest.raises(TooSmallException):
        validate_field_length(['a'], 2, 5)


def test_list_length_empty() -> None:
    with pytest.raises(TooSmallException):
        validate_field_length([], 1)
