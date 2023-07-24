import importlib
import importlib.machinery
import inspect
import os
import sys
from types import ModuleType
from typing import Dict, List, Optional, Set, Tuple
from weakref import finalize


class WeakReference:
    pass


def _finalize_callback(parent: ModuleType, names: List[str]) -> None:
    for name in names:
        parent.__dict__.pop(name, None)


class ImportLoader(importlib.machinery.SourceFileLoader):
    module_cache: Dict[str, ModuleType]
    module_aliases: Set[str]

    def __init__(self, fullname: str, path: str) -> None:
        super().__init__(fullname, path)
        self.module_cache = {}
        self.module_aliases = set()

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> Optional[ModuleType]:
        module: Optional[ModuleType] = self.module_cache.get(spec.name)
        if module:
            return module

        result = super().create_module(spec)
        return result

    def exec_module(self, module: ModuleType) -> None:
        name = ""
        try:
            if module.__spec__:
                name = module.__spec__.name
        except Exception:
            pass
        if not name:
            name = module.__name__

        super().exec_module(module)

        if sys.modules.get(name):
            self.module_cache[name] = sys.modules[name]
            for alias in self.module_aliases:
                if sys.modules.get(alias) is not sys.modules[name]:
                    sys.modules[alias] = sys.modules[name]

        parent_name = name.rpartition(".")[0]
        if parent_name:
            try:
                parent = sys.modules[parent_name]
                names = [alias.rpartition(".")[2] for alias in self.module_aliases]
                for tail_name in names:
                    if tail_name in parent.__dict__:
                        parent.__dict__.pop(tail_name)

                    parent.__dict__[tail_name] = WeakReference()
                    finalize(parent.__dict__[tail_name], _finalize_callback, parent, names)
            except KeyError:
                pass


class ImportFinder(importlib.machinery.FileFinder):
    _path_mtime: float
    module_name_mapping: Dict[str, str]
    reversed_module_name_mapping: Dict[str, Set[str]]
    spec_cache: Dict[Tuple[str, float], importlib.machinery.ModuleSpec]

    def __init__(self, path: str, module_name_mapping: Dict[str, str]) -> None:
        self.module_name_mapping = module_name_mapping
        self.reversed_module_name_mapping = {}
        self.spec_cache = {}

        for k, v in module_name_mapping.items():
            self.reversed_module_name_mapping[v] = self.reversed_module_name_mapping.get(v, set()) | set([k])

        super().__init__(
            path,
            (ImportLoader, importlib.machinery.SOURCE_SUFFIXES),
            (importlib.machinery.SourceFileLoader, importlib.machinery.SOURCE_SUFFIXES),
            (importlib.machinery.SourcelessFileLoader, importlib.machinery.BYTECODE_SUFFIXES),
        )

    def install(self) -> None:
        sys.path_importer_cache[self.path] = self

    def find_spec(self, fullname: str, target: Optional[ModuleType] = None) -> Optional[importlib.machinery.ModuleSpec]:
        fullname_ = self.module_name_mapping.get(fullname, fullname)

        spec = super().find_spec(fullname_, target=target)
        cached_spec = None

        if (
            fullname_ != fullname
            and sys.modules.get(fullname_, None) is not None
            and sys.modules.get(fullname, None) is None
        ):
            cached_spec = self.spec_cache.get((fullname_, self._path_mtime))

        if cached_spec:
            return cached_spec

        if not spec:
            return spec

        self.spec_cache[(fullname_, self._path_mtime)] = spec
        if isinstance(spec.loader, ImportLoader):
            spec.loader.module_aliases.add(fullname_)

        for name in self.reversed_module_name_mapping.get(fullname_, []):
            self.spec_cache[(name, self._path_mtime)] = spec
            if isinstance(spec.loader, ImportLoader):
                spec.loader.module_aliases.add(name)

        return spec


def _install_import_finder(module_name_mapping: Dict[str, str]) -> None:
    path = os.path.dirname(os.path.abspath(inspect.stack()[1].filename))
    ImportFinder(path, module_name_mapping).install()


__all__ = ["ImportFinder", "_install_import_finder"]
