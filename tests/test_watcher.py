import asyncio
import os
import sys
from typing import Any, Dict, List, Union

from tomodachi.watcher import Watcher


def test_watcher_auto_root() -> None:
    watcher = Watcher()
    assert watcher.root == [os.path.realpath(sys.argv[0].rsplit("/", 1)[0])]


def test_watcher_empty_directory() -> None:
    root_path = "{}/tests/watcher_root/empty".format(os.path.realpath(os.getcwd()))
    watcher = Watcher(root=[root_path])
    assert len(watcher.root) == 1
    assert isinstance(watcher.watched_files, dict)
    assert len(watcher.watched_files) == 0


def test_watcher_default_ignored_directory() -> None:
    root_path = "{}/tests/watcher_root/__tmp__".format(os.path.realpath(os.getcwd()))
    watcher = Watcher(root=[root_path])
    assert len(watcher.root) == 1
    assert isinstance(watcher.watched_files, dict)
    assert len(watcher.watched_files) == 0


def test_watcher_configurable_ignored_directory() -> None:
    root_path = "{}/tests/watcher_root/configurable_ignored".format(os.path.realpath(os.getcwd()))
    watcher = Watcher(root=[root_path])
    assert len(watcher.root) == 1
    assert isinstance(watcher.watched_files, dict)
    assert len(watcher.watched_files) == 1

    watcher = Watcher(
        root=[root_path], configuration={"options": {"watcher": {"ignored_dirs": ["configurable_ignored"]}}}
    )
    assert len(watcher.root) == 1
    assert isinstance(watcher.watched_files, dict)
    assert len(watcher.watched_files) == 0


def test_watcher_callback(loop: Any) -> None:
    root_path = "{}/tests/watcher_root".format(os.path.realpath(os.getcwd()))
    watcher = Watcher(root=[root_path])
    assert len(watcher.root) == 1
    assert isinstance(watcher.watched_files, dict)
    assert len(watcher.watched_files) == 2

    result = watcher.update_watched_files()
    assert result == {}

    watcher.watched_files = {"_test": 0}
    watcher.watched_files_crc = {"_test": ""}
    result = watcher.update_watched_files(reindex=True)
    assert len(result.get("added", 0)) == 2
    assert len(result.get("removed", 0)) == 1
    assert len(result.get("updated", 0)) == 0

    class Test:
        callbacks_run: Dict[int, bool] = {}

        @classmethod
        async def _async(cls) -> None:
            async def cb1(updated_files: Union[List, set]) -> None:
                cls.callbacks_run[1] = True

            async def cb2(updated_files: Union[List, set]) -> None:
                cls.callbacks_run[2] = True

            task = await watcher.watch(callback_func=cb1)
            await asyncio.sleep(1.0)
            task.cancel()

            watcher.watched_files = {"_test": 0}
            watcher.watched_files_crc = {"_test": ""}
            task = await watcher.watch(callback_func=cb2)
            await asyncio.sleep(1.0)
            task.cancel()

            assert cls.callbacks_run.get(1) is None
            assert cls.callbacks_run.get(2) is True

    loop.run_until_complete(Test._async())
