import pytest
import logging
import tomodachi
import tomodachi.cli


def test_cli_help_command_method(capsys):
    cli = tomodachi.cli.CLI()
    with pytest.raises(SystemExit):
        cli.help_command()
    out, err = capsys.readouterr()
    assert err == ''
    assert out == cli.help_command_usage() + "\n"


def test_cli_run_command_method_no_args(capsys):
    cli = tomodachi.cli.CLI()
    with pytest.raises(SystemExit):
        cli.run_command([])
    out, err = capsys.readouterr()
    assert err == ''
    assert out == cli.run_command_usage() + "\n"


def testcli_start_service(monkeypatch, capsys):
    monkeypatch.setattr(logging.root, 'handlers', [])

    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(['tomodachi', 'run', 'tests/dummy_service.py'])

    out, err = capsys.readouterr()
    assert err != ''
    assert 'Starting services' in out
    assert 'tomodachi/{}'.format(tomodachi.__version__) in out


def testcli_start_service_production_mode(monkeypatch, capsys):
    monkeypatch.setattr(logging.root, 'handlers', [])

    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(['tomodachi', 'run', 'tests/dummy_service.py', '--production'])

    out, err = capsys.readouterr()
    assert err != ''
    assert out == '\x08\x08\r'


def testcli_start_service_with_config(monkeypatch, capsys):
    monkeypatch.setattr(logging.root, 'handlers', [])

    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(['tomodachi', 'run', 'tests/dummy_service.py', '-c', 'tests/config_file.json'])

    out, err = capsys.readouterr()
    assert 'Starting services' in out
    assert 'tomodachi/{}'.format(tomodachi.__version__) in out


def testcli_start_service_with_non_existing_config(monkeypatch, capsys):
    monkeypatch.setattr(logging.root, 'handlers', [])

    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(['tomodachi', 'run', 'tests/dummy_service.py', '-c', 'tests/without_config_file.json'])

    out, err = capsys.readouterr()
    assert 'Starting services' not in out
    assert 'tomodachi/{}'.format(tomodachi.__version__) not in out
