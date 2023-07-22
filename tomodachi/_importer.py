import importlib.machinery
import inspect
import os
import sys
from types import ModuleType
from typing import Dict, Optional


class ImportFinder(importlib.machinery.FileFinder):
    def __init__(self, path: str, module_name_mapping: Dict[str, str]) -> None:
        self.module_name_mapping = module_name_mapping
        super().__init__(
            path,
            (importlib.machinery.SourceFileLoader, importlib.machinery.SOURCE_SUFFIXES),
            (importlib.machinery.SourcelessFileLoader, importlib.machinery.BYTECODE_SUFFIXES),
        )

    def install(self) -> None:
        sys.path_importer_cache[self.path] = self

    def find_spec(self, fullname: str, target: Optional[ModuleType] = None) -> Optional[importlib.machinery.ModuleSpec]:
        fullname = self.module_name_mapping.get(fullname, fullname)
        return super().find_spec(fullname, target=target)


def _install_import_finder(module_name_mapping: Dict[str, str]) -> None:
    path = os.path.dirname(os.path.abspath(inspect.stack()[1].filename))
    ImportFinder(path, module_name_mapping).install()


__all__ = ["ImportFinder", "_install_import_finder"]
