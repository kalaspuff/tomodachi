from decimal import Decimal
from tomodachi.config import merge_dicts, parse_config_files


def test_merge_dicts() -> None:
    dict1 = {
        'number_list': [1, 3, 5],
        'string': 'string',
        'dict': {
            'value_in_dict': True
        },
        'replace_value': 100
    }

    dict2 = {
        'number_list': [2, 10],
        'dict': {
            'another_value_in_dict': Decimal(10.0)
        },
        'replace_value': 200
    }

    result = merge_dicts(dict1, dict2)
    expected_result = {
        'number_list': [1, 3, 5, 2, 10],
        'string': 'string',
        'dict': {
            'value_in_dict': True,
            'another_value_in_dict': Decimal(10.0)
        },
        'replace_value': 200
    }
    assert result == expected_result


def test_parse_config_file() -> None:
    result = parse_config_files(['tests/configs/config_file.json'])
    expected_result = {
        'options': {
            'http': {
                'port': 4711,
                'access_log': True
            }
        },
        'uuid': '21a24416-1427-4603-c7c9-0ff8ab1f1c20'
    }
    assert result == expected_result


def test_parse_no_config_file() -> None:
    result = parse_config_files([])
    assert result is None
