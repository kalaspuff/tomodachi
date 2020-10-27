import asyncio
import logging
import os
import sys
import zlib
from typing import Any, Callable, Dict, List, Optional


def crc(file_path: str) -> str:
    prev = 0
    for line in open(file_path, "rb"):
        prev = zlib.crc32(line, prev)

    return "%X" % (prev & 0xFFFFFFFF)


class Watcher(object):
    def __init__(self, root: Optional[List] = None, configuration: Optional[Dict] = None) -> None:
        self.watched_files: Dict[str, float] = {}
        self.watched_files_crc: Dict[str, str] = {}
        self.root: List[str] = []
        self.ignored_dirs = ["__pycache__", ".git", ".svn", "__ignored__", "__temporary__", "__tmp__"]
        self.watched_file_endings = [".py", ".pyi", ".json", ".yml", ".html", ".phtml"]

        if not root:
            directory = os.path.realpath(sys.argv[0].rsplit("/", 1)[0])
            self.root = [os.path.dirname(directory) if os.path.isfile(directory) else directory]
        else:
            self.root = root

        if configuration is not None:
            ignored_dirs_list = configuration.get("options", {}).get("watcher", {}).get("ignored_dirs", [])
            if ignored_dirs_list:
                self.ignored_dirs.extend(ignored_dirs_list)

            watched_file_endings_list = (
                configuration.get("options", {}).get("watcher", {}).get("watched_file_endings", [])
            )
            if watched_file_endings_list:
                self.watched_file_endings.extend(watched_file_endings_list)

        self.update_watched_files()

    def update_watched_files(self, reindex: bool = False) -> Dict:
        watched_files: Dict[str, float] = {}
        watched_files_crc: Dict[str, str] = {}
        if not self.watched_files or reindex:
            for r in self.root:
                for root, dirs, files in os.walk(r, topdown=True):
                    dirs[:] = [d for d in dirs if d not in self.ignored_dirs]
                    for file in files:
                        file_path = os.path.join(root, file)
                        _dir = os.path.dirname(file_path)
                        if (
                            _dir not in self.ignored_dirs
                            and not any(
                                [
                                    os.path.join(root, _dir).endswith("/{}".format(ignored_dir))
                                    or "/{}/".format(ignored_dir) in os.path.join(root, _dir)
                                    for ignored_dir in self.ignored_dirs
                                ]
                            )
                            and any([file.endswith(ending) for ending in self.watched_file_endings])
                            and "/." not in file_path
                        ):
                            watched_files[file_path] = os.path.getmtime(file_path)
                            watched_files_crc[file_path] = (
                                crc(file_path)
                                if watched_files[file_path] != self.watched_files.get(file_path)
                                else self.watched_files_crc.get(file_path, "")
                            )
        else:
            for file_path, mtime in self.watched_files.items():
                try:
                    watched_files[file_path] = os.path.getmtime(file_path)
                    watched_files_crc[file_path] = (
                        crc(file_path)
                        if watched_files[file_path] != self.watched_files.get(file_path)
                        else self.watched_files_crc.get(file_path, "")
                    )
                except FileNotFoundError:
                    pass

        if self.watched_files and self.watched_files != watched_files and self.watched_files_crc == watched_files_crc:
            self.watched_files = watched_files

        if self.watched_files and self.watched_files != watched_files:
            added = [
                k[((len(self.root[0]) if k.startswith(self.root[0]) else -1) + 1) :]
                for k in watched_files.keys()
                if k not in self.watched_files.keys()
            ]
            removed = [
                k[((len(self.root[0]) if k.startswith(self.root[0]) else -1) + 1) :]
                for k in self.watched_files.keys()
                if k not in watched_files.keys()
            ]
            updated = [
                k[((len(self.root[0]) if k.startswith(self.root[0]) else -1) + 1) :]
                for k in watched_files.keys()
                if k in self.watched_files.keys() and self.watched_files[k] != watched_files[k]
            ]
            self.watched_files = watched_files
            self.watched_files_crc = watched_files_crc
            return {"added": added, "removed": removed, "updated": updated}

        self.watched_files = watched_files
        self.watched_files_crc = watched_files_crc

        return {}

    async def watch(self, loop: asyncio.AbstractEventLoop = None, callback_func: Optional[Callable] = None) -> Any:
        _loop: Any = asyncio.get_event_loop() if not loop else loop

        async def _watch_loop() -> None:
            loop_counter = 0
            while True:
                loop_counter = (loop_counter + 1) % 20
                updated_files = self.update_watched_files(reindex=(loop_counter == 0))
                if updated_files:
                    added = updated_files.get("added")
                    removed = updated_files.get("removed")
                    updated = updated_files.get("updated")
                    if removed:
                        if len(removed) > 2:
                            removed[2] = "..."
                        logging.getLogger("watcher.files").warning(
                            "Removed files: {}".format(", ".join([file for file in removed][0:3]))
                        )
                    if added:
                        if len(added) > 2:
                            added[2] = "..."
                        logging.getLogger("watcher.files").warning(
                            "New files: {}".format(", ".join([file for file in added][0:3]))
                        )
                    if updated:
                        if len(updated) > 2:
                            updated[2] = "..."
                        logging.getLogger("watcher.files").warning(
                            "Updated files: {}".format(", ".join([file for file in updated][0:3]))
                        )

                    if callback_func:
                        await callback_func(set([file for file in added] + [file for file in updated]))
                await asyncio.sleep(0.5)

        return _loop.create_task(_watch_loop())
