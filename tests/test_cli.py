import pytest
import logging
from typing import Any
import tomodachi
import tomodachi.cli


def test_cli_help_command_method(capsys: Any) -> None:
    cli = tomodachi.cli.CLI()
    with pytest.raises(SystemExit):
        cli.help_command()
    out, err = capsys.readouterr()
    assert err == ''
    assert out == cli.help_command_usage() + "\n"


def test_cli_version_command_method(capsys: Any) -> None:
    cli = tomodachi.cli.CLI()
    with pytest.raises(SystemExit):
        cli.version_command()
    out, err = capsys.readouterr()
    assert err == ''
    assert out == 'tomodachi/{}'.format(tomodachi.__version__) + "\n"


def test_cli_run_command_method_no_args(capsys: Any) -> None:
    cli = tomodachi.cli.CLI()
    with pytest.raises(SystemExit):
        cli.run_command([])
    out, err = capsys.readouterr()
    assert err == ''
    assert out == cli.run_command_usage() + "\n"


def test_cli_entrypoint_no_arguments(monkeypatch: Any, capsys: Any) -> None:
    cli = tomodachi.cli.CLI()
    monkeypatch.setattr(logging.root, 'handlers', [])

    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint()

    out, err = capsys.readouterr()
    assert err == ''
    assert out == cli.help_command_usage() + "\n"


def test_cli_entrypoint_print_help(monkeypatch: Any, capsys: Any) -> None:
    cli = tomodachi.cli.CLI()
    monkeypatch.setattr(logging.root, 'handlers', [])

    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(['tomodachi', '-h'])

    out, err = capsys.readouterr()
    assert err == ''
    assert out == cli.help_command_usage() + "\n"


def test_cli_entrypoint_print_version(monkeypatch: Any, capsys: Any) -> None:
    cli = tomodachi.cli.CLI()
    monkeypatch.setattr(logging.root, 'handlers', [])

    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(['tomodachi', '-v'])

    out, err = capsys.readouterr()
    assert err == ''
    assert out == 'tomodachi/{}'.format(tomodachi.__version__) + "\n"


def test_cli_entrypoint_invalid_arguments_show_help(monkeypatch: Any, capsys: Any) -> None:
    cli = tomodachi.cli.CLI()
    monkeypatch.setattr(logging.root, 'handlers', [])

    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(['tomodachi', '--invalid'])

    out, err = capsys.readouterr()
    assert err == ''
    assert out == cli.help_command_usage() + "\n"


def test_cli_entrypoint_invalid_subcommand_show_help(monkeypatch: Any, capsys: Any) -> None:
    cli = tomodachi.cli.CLI()
    monkeypatch.setattr(logging.root, 'handlers', [])

    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(['tomodachi', 'invalidsubcommand'])

    out, err = capsys.readouterr()
    assert err == ''
    assert out == cli.help_command_usage() + "\n"


def test_cli_start_service(monkeypatch: Any, capsys: Any) -> None:
    monkeypatch.setattr(logging.root, 'handlers', [])

    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(['tomodachi', 'run', 'tests/services/auto_closing_service.py'])

    out, err = capsys.readouterr()
    assert err != ''
    assert 'Starting services' in out
    assert 'tomodachi/{}'.format(tomodachi.__version__) in out


def test_cli_start_service_production_mode(monkeypatch: Any, capsys: Any) -> None:
    monkeypatch.setattr(logging.root, 'handlers', [])

    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(['tomodachi', 'run', 'tests/services/auto_closing_service.py', '--production'])

    out, err = capsys.readouterr()
    assert err != ''
    assert out == ''


def test_cli_start_service_with_config(monkeypatch: Any, capsys: Any) -> None:
    monkeypatch.setattr(logging.root, 'handlers', [])

    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(['tomodachi', 'run', 'tests/services/auto_closing_service.py', '-c', 'tests/configs/config_file.json'])

    out, err = capsys.readouterr()
    assert 'Starting services' in out
    assert 'tomodachi/{}'.format(tomodachi.__version__) in out


def test_cli_start_service_with_non_existing_config(monkeypatch: Any, capsys: Any) -> None:
    monkeypatch.setattr(logging.root, 'handlers', [])

    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(['tomodachi', 'run', 'tests/services/auto_closing_service.py', '-c', 'tests/configs/without_config_file.json'])

    out, err = capsys.readouterr()
    assert 'Starting services' not in out
    assert 'tomodachi/{}'.format(tomodachi.__version__) not in out
    assert 'Invalid config file' in out


def test_cli_start_service_with_invalid_config(monkeypatch: Any, capsys: Any) -> None:
    monkeypatch.setattr(logging.root, 'handlers', [])

    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(['tomodachi', 'run', 'tests/services/auto_closing_service.py', '-c', 'tests/configs/invalid_config_file.json'])

    out, err = capsys.readouterr()
    assert 'Starting services' not in out
    assert 'tomodachi/{}'.format(tomodachi.__version__) not in out
    assert 'Invalid config file, invalid JSON format' in out


def test_cli_start_service_without_config_arguments(monkeypatch: Any, capsys: Any) -> None:
    monkeypatch.setattr(logging.root, 'handlers', [])

    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(['tomodachi', 'run', 'tests/services/auto_closing_service.py', '-c'])

    out, err = capsys.readouterr()
    assert 'Starting services' not in out
    assert 'tomodachi/{}'.format(tomodachi.__version__) not in out
    assert 'Missing config file on command line' in out
