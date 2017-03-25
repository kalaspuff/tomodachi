import asyncio
import os
import sys
import logging


class Watcher(object):
    watched_files = None
    root = None

    def __init__(self, root=None):
        if not root:
            directory = os.path.realpath(sys.argv[0].rsplit('/', 1)[0])
            if os.path.isfile(directory):
                directory = os.path.dirname(directory)
            self.root = [directory]
        else:
            self.root = root
        self.update_watched_files()

    def update_watched_files(self):
        watched_files = {}
        for r in self.root:
            for root, dirs, files in os.walk(r):
                for file in files:
                    if file.endswith(".py") and '/.' not in os.path.join(root, file):
                        watched_files[(os.path.join(root, file))] = os.path.getmtime(os.path.join(root, file))
                for _dir in dirs:
                    if '__pycache__' not in os.path.join(root, _dir) and '/.' not in os.path.join(root, _dir):
                        watched_files[(os.path.join(root, _dir))] = os.path.getmtime(os.path.join(root, _dir))

        if self.watched_files and self.watched_files != watched_files:
            added = [k[(len(self.root) + 1):] for k in watched_files.keys() if k not in self.watched_files.keys()]
            removed = [k[(len(self.root) + 1):] for k in self.watched_files.keys() if k not in watched_files.keys()]
            updated = [k[(len(self.root) + 1):] for k in watched_files.keys() if k in self.watched_files.keys() and self.watched_files[k] != watched_files[k]]
            self.watched_files = watched_files
            return {'added': added, 'removed': removed, 'updated': updated}
        self.watched_files = watched_files
        return False

    async def watch(self, loop=None, callback_func=None):
        if not loop:
            loop = asyncio.get_event_loop()

        async def _watch_loop():
            while True:
                updated_files = self.update_watched_files()
                if updated_files:
                    added = updated_files.get('added')
                    removed = updated_files.get('removed')
                    updated = updated_files.get('updated')
                    if removed:
                        if len(removed) > 2:
                            removed[2] = '...'
                        logging.getLogger('watcher.files').warn('Removed files: {}'.format(', '.join([file for file in removed][0:3])))
                    if added:
                        if len(added) > 2:
                            added[2] = '...'
                        logging.getLogger('watcher.files').warn('New files: {}'.format(', '.join([file for file in added][0:3])))
                    if updated:
                        if len(updated) > 2:
                            updated[2] = '...'
                        logging.getLogger('watcher.files').warn('Updated files: {}'.format(', '.join([file for file in updated][0:3])))

                    if callback_func:
                        await callback_func()
                await asyncio.sleep(0.5)

        return loop.create_task(_watch_loop())
