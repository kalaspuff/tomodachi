import os
import asyncio
import sys
from tomodachi.watcher import Watcher


def test_watcher_auto_root():
    watcher = Watcher()
    assert watcher.root == [os.path.realpath(sys.argv[0].rsplit('/', 1)[0])]


def test_watcher_empty_directory():
    root_path = '{}/tests/watcher_root/empty'.format(os.path.realpath(os.getcwd()))
    watcher = Watcher(root=[root_path])
    assert len(watcher.root) == 1
    assert isinstance(watcher.watched_files, dict)
    assert len(watcher.watched_files) == 0


def test_watcher_callback():
    root_path = '{}/tests/watcher_root'.format(os.path.realpath(os.getcwd()))
    watcher = Watcher(root=[root_path])
    assert len(watcher.root) == 1
    assert isinstance(watcher.watched_files, dict)
    assert len(watcher.watched_files) == 1

    result = watcher.update_watched_files()
    assert result is False

    watcher.watched_files = {'_test': 0}
    result = watcher.update_watched_files()
    assert len(result.get('added')) == 1
    assert len(result.get('removed')) == 1
    assert len(result.get('updated')) == 0

    class Test():
        callbacks_run = {}

        @classmethod
        async def _async(cls):

            async def cb1():
                cls.callbacks_run[1] = True

            async def cb2():
                cls.callbacks_run[2] = True

            task = await watcher.watch(callback_func=cb1)
            await asyncio.sleep(1.0)
            task.cancel()

            watcher.watched_files = {'_test': 0}
            task = await watcher.watch(callback_func=cb2)
            await asyncio.sleep(1.0)
            task.cancel()

            assert cls.callbacks_run.get(1) is None
            assert cls.callbacks_run.get(2) is True

    loop = asyncio.get_event_loop()
    loop.run_until_complete(Test._async())
