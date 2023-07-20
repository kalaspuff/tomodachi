from typing import Any

import pytest

import tomodachi
import tomodachi.cli


def test_cli_help_command_method(capsys: Any) -> None:
    cli = tomodachi.cli.CLI()
    with pytest.raises(SystemExit):
        cli.help_command()
    out, err = capsys.readouterr()
    assert (out + err) == cli.help_command_usage() + "\n"


def test_cli_version_command_method(capsys: Any) -> None:
    cli = tomodachi.cli.CLI()
    with pytest.raises(SystemExit):
        cli.version_command()
    out, err = capsys.readouterr()
    assert (out + err) == "tomodachi {}".format(tomodachi.__version__) + "\n"


def test_cli_run_command_method_no_args(capsys: Any) -> None:
    cli = tomodachi.cli.CLI()
    with pytest.raises(SystemExit):
        cli.run_command([])
    out, err = capsys.readouterr()
    assert (out + err) == cli.run_command_usage() + "\n"


def test_cli_entrypoint_no_arguments(capsys: Any) -> None:
    cli = tomodachi.cli.CLI()

    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint()

    out, err = capsys.readouterr()
    assert (out + err) == cli.help_command_usage() + "\n"


def test_cli_entrypoint_print_help(capsys: Any) -> None:
    cli = tomodachi.cli.CLI()

    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(["tomodachi", "-h"])

    out, err = capsys.readouterr()
    assert (out + err) == cli.help_command_usage() + "\n"


def test_cli_entrypoint_print_dependency_versions(capsys: Any) -> None:
    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(["tomodachi", "--dependency-versions"])

    out, err = capsys.readouterr()
    assert (out + err) != "tomodachi/{}".format(tomodachi.__version__) + "\n"

    import aiobotocore

    assert "aiobotocore/{}".format(aiobotocore.__version__) + "\n" in (out + err)


def test_cli_entrypoint_print_version(capsys: Any) -> None:
    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(["tomodachi", "-v"])

    out, err = capsys.readouterr()
    assert (out + err) == "tomodachi {}".format(tomodachi.__version__) + "\n"


def test_cli_entrypoint_invalid_arguments_show_help(capsys: Any) -> None:
    cli = tomodachi.cli.CLI()

    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(["tomodachi", "--invalid"])

    out, err = capsys.readouterr()
    assert (out + err) == cli.help_command_usage() + "\n"


def test_cli_entrypoint_invalid_subcommand_show_help(capsys: Any) -> None:
    cli = tomodachi.cli.CLI()

    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(["tomodachi", "invalidsubcommand"])

    out, err = capsys.readouterr()
    assert (out + err) == cli.help_command_usage() + "\n"


def test_cli_start_service_stopped_with_sigterm(capsys: Any) -> None:
    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(["tomodachi", "run", "tests/services/auto_closing_service_sigterm.py"])

    out, err = capsys.readouterr()
    assert "initializing service instance" in (out + err)
    assert "tomodachi versions      ⇢ {}".format(tomodachi.__version__) in (out + err)


def test_cli_start_service_stopped_with_sigint(capsys: Any) -> None:
    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(["tomodachi", "run", "tests/services/auto_closing_service_sigint.py"])

    out, err = capsys.readouterr()
    assert "initializing service instance" in (out + err)
    assert "tomodachi version      ⇢ {}".format(tomodachi.__version__) in (out + err)


def test_cli_start_service_stopped_with_exit_call(capsys: Any) -> None:
    with pytest.raises(SystemExit) as pytest_wrapped_exception:
        tomodachi.cli.cli_entrypoint(["tomodachi", "run", "tests/services/auto_closing_service_exit_call.py"])

    assert pytest_wrapped_exception.type == SystemExit
    assert pytest_wrapped_exception.value.code == 0

    out, err = capsys.readouterr()
    assert "initializing service instance" in (out + err)
    assert "tomodachi version      ⇢ {}".format(tomodachi.__version__) in (out + err)


def test_cli_start_service_stopped_with_exit_code_1(capsys: Any) -> None:
    with pytest.raises(SystemExit) as pytest_wrapped_exception:
        tomodachi.cli.cli_entrypoint(["tomodachi", "run", "tests/services/auto_closing_service_exit_code_1.py"])

    assert pytest_wrapped_exception.type == SystemExit
    assert pytest_wrapped_exception.value.code == 1

    out, err = capsys.readouterr()
    assert "initializing service instance" in (out + err)
    assert "tomodachi version      ⇢ {}".format(tomodachi.__version__) in (out + err)


def test_cli_start_service_stopped_with_exit_code_128(capsys: Any) -> None:
    with pytest.raises(SystemExit) as pytest_wrapped_exception:
        tomodachi.cli.cli_entrypoint(["tomodachi", "run", "tests/services/auto_closing_service_exit_code_128.py"])

    assert pytest_wrapped_exception.type == SystemExit
    assert pytest_wrapped_exception.value.code == 128

    out, err = capsys.readouterr()
    assert "initializing service instance" in (out + err)
    assert "tomodachi version      ⇢ {}".format(tomodachi.__version__) in (out + err)


def test_cli_start_exception_service(capsys: Any) -> None:
    with pytest.raises(SystemExit) as pytest_wrapped_exception:
        tomodachi.cli.cli_entrypoint(["tomodachi", "run", "tests/services/exception_service.py"])

    assert pytest_wrapped_exception.type == SystemExit
    assert pytest_wrapped_exception.value.code == 1

    out, err = capsys.readouterr()
    assert "initializing service instance" in (out + err)
    assert "failed to initialize instance" not in (out + err)
    assert "tomodachi version      ⇢ {}".format(tomodachi.__version__) in (out + err)
    assert "fail in _start_service()" in (out + err)


def test_cli_start_exception_service_init(capsys: Any) -> None:
    with pytest.raises(SystemExit) as pytest_wrapped_exception:
        tomodachi.cli.cli_entrypoint(["tomodachi", "run", "tests/services/exception_service_init.py"])

    assert pytest_wrapped_exception.type == SystemExit
    assert pytest_wrapped_exception.value.code == 1

    out, err = capsys.readouterr()
    assert "failed to initialize instance" in (out + err)
    assert "initializing service instance" not in (out + err)
    assert "tomodachi version      ⇢ {}".format(tomodachi.__version__) in (out + err)
    assert "fail in __init__()" in (out + err)


def test_cli_start_service_production_mode(capsys: Any) -> None:
    with pytest.raises(SystemExit) as pytest_wrapped_exception:
        tomodachi.cli.cli_entrypoint(
            ["tomodachi", "run", "tests/services/auto_closing_service_exit_call.py", "--production"]
        )

    assert pytest_wrapped_exception.type == SystemExit
    assert pytest_wrapped_exception.value.code == 0

    out, err = capsys.readouterr()
    assert "initializing service instance" in (out + err)
    assert "starting the service" in (out + err)
    assert "enabled handler functions" in (out + err)
    assert "tomodachi.exit [0] was called" in (out + err)
    assert "stopping service" in (out + err)
    assert "terminated service" in (out + err)


def test_cli_start_service_with_config(capsys: Any) -> None:
    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(
            [
                "tomodachi",
                "run",
                "tests/services/auto_closing_service_exit_call.py",
                "-c",
                "tests/configs/config_file.json",
            ]
        )

    out, err = capsys.readouterr()
    assert "initializing service instance" in (out + err)
    assert "tomodachi version      ⇢ {}".format(tomodachi.__version__) in (out + err)


def test_cli_start_service_with_non_existing_config(capsys: Any) -> None:
    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(
            [
                "tomodachi",
                "run",
                "tests/services/auto_closing_service_exit_call.py",
                "-c",
                "tests/configs/without_config_file.json",
            ]
        )

    out, err = capsys.readouterr()
    assert "initializing service instance" not in (out + err)
    assert "tomodachi version      ⇢ {}".format(tomodachi.__version__) not in (out + err)
    assert "Invalid config file" in (out + err)


def test_cli_start_service_with_invalid_config(capsys: Any) -> None:
    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(
            [
                "tomodachi",
                "run",
                "tests/services/auto_closing_service_exit_call.py",
                "-c",
                "tests/configs/invalid_config_file.json",
            ]
        )

    out, err = capsys.readouterr()
    assert "initializing service instance" not in (out + err)
    assert "tomodachi version      ⇢ {}".format(tomodachi.__version__) not in (out + err)
    assert "Invalid config file, invalid JSON format" in (out + err)


def test_cli_start_service_without_config_arguments(capsys: Any) -> None:
    with pytest.raises(SystemExit):
        tomodachi.cli.cli_entrypoint(["tomodachi", "run", "tests/services/auto_closing_service_exit_call.py", "-c"])

    out, err = capsys.readouterr()
    assert "initializing service instance" not in (out + err)
    assert "tomodachi version      ⇢ {}".format(tomodachi.__version__) not in (out + err)
    assert "Missing config file on command line" in (out + err)
