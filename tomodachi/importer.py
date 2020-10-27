import importlib
import importlib.util
import logging
import os
import sys
from types import ModuleType
from typing import Any  # noqa


class ServicePackageError(ImportError):
    pass


try:
    if ModuleNotFoundError:
        pass
except Exception:

    class ModuleNotFoundError(ImportError):
        pass


class ServiceImporter(object):
    @classmethod
    def import_service_file(cls, file_name: str) -> ModuleType:
        cwd = os.getcwd()
        file_path = "{}/{}.py".format(os.path.realpath(cwd), file_name)
        if file_path.endswith(".py.py"):
            file_path = file_path[:-3]
        try:
            sys.path.insert(0, cwd)
            sys.path.insert(0, os.path.dirname(os.path.dirname(file_path)))
            if file_path.endswith(".py") and not os.path.isfile(file_path):
                raise OSError("No such service file")
            elif not file_path.endswith(".py") and not os.path.isfile("{}.py".format(file_path)):
                raise OSError("No such service file")
            try:
                spec: Any = importlib.util.find_spec(
                    ".{}".format(file_path.rsplit("/", 1)[1])[:-3], package=os.path.dirname(file_path).rsplit("/", 1)[1]
                )
                if not spec:
                    # package name already taken, imported service not part of a package
                    spec = importlib.util.spec_from_file_location(file_name, file_path)
            except AttributeError as e:
                # package name already taken, imported service not part of a package
                try:
                    spec = importlib.util.spec_from_file_location(file_name, file_path)
                except Exception:
                    raise e
            except ModuleNotFoundError as e:  # noqa
                file_path_package_name = file_path[:-3] if file_path.endswith(".py") else file_path
                if str(e) == "__path__ attribute not found on '{}' while trying to find '{}'".format(
                    file_path_package_name.rsplit("/", 2)[1], ".".join(file_path_package_name.rsplit("/", 2)[1:])
                ):
                    logging.getLogger("import").warning(
                        'Invalid service package/parent name, may conflict with Python internals: "{}" - change parent folder name'.format(
                            file_path.rsplit("/", 2)[1]
                        )
                    )
                    raise ServicePackageError from e
                if str(e) == "__path__ attribute not found on '{}'while trying to find '{}'".format(
                    file_path_package_name.rsplit("/", 2)[1], ".".join(file_path_package_name.rsplit("/", 2)[1:])
                ):
                    logging.getLogger("import").warning(
                        'Invalid service package/parent name, may conflict with Python internals: "{}" - change parent folder name'.format(
                            file_path.rsplit("/", 2)[1]
                        )
                    )
                    raise ServicePackageError from e
                raise e
            if not spec:
                raise OSError
            service_import = importlib.util.module_from_spec(spec)
            try:
                importlib.reload(service_import)
                service_import = importlib.util.module_from_spec(spec)
            except ImportError:
                pass
            if not spec.loader:
                raise OSError
            try:
                if service_import:
                    service_import_name = (
                        service_import.__name__[:-3]
                        if service_import.__name__.endswith(".py")
                        else service_import.__name__
                    )
                else:
                    service_import_name = ""
                spec.loader.exec_module(service_import)
            except ImportError as e:
                if service_import_name and str(e) == "No module named '{}'".format(service_import_name):
                    logging.getLogger("import").warning(
                        'Invalid service package/parent name, may conflict with Python internals: "{}" - change parent folder name'.format(
                            file_path.rsplit("/", 2)[1]
                        )
                    )
                    raise ServicePackageError from e
                if str(e) == "attempted relative import with no known parent package":
                    logging.getLogger("import").warning(
                        'Invalid service package/parent name, may conflict with Python internals: "{}" - change parent folder name'.format(
                            file_path.rsplit("/", 2)[1]
                        )
                    )
                    raise ServicePackageError from e
                raise e
            except SystemError as e:
                if service_import_name and str(
                    e
                ) == "Parent module '{}' not loaded, cannot perform relative import".format(service_import_name):
                    logging.getLogger("import").warning(
                        'Invalid service package/parent name, may conflict with Python internals: "{}" - change parent folder name'.format(
                            file_path.rsplit("/", 2)[1]
                        )
                    )
                    raise ServicePackageError from e
                if str(e) == "Parent module '' not loaded, cannot perform relative import":
                    logging.getLogger("import").warning(
                        'Invalid service package/parent name, may conflict with Python internals: "{}" - change parent folder name'.format(
                            file_path.rsplit("/", 2)[1]
                        )
                    )
                    raise ServicePackageError from e
                raise e
        except (ImportError, ModuleNotFoundError) as e:  # noqa
            if file_name.endswith(".py.py"):
                return cls.import_service_file(file_name[:-3])
            if file_name.endswith(".py") and isinstance(e, ModuleNotFoundError):  # noqa
                return cls.import_service_file(file_name[:-3])
            if file_name.endswith(".py"):
                file_name = file_name[:-3]
            logging.getLogger("import").warning(
                'Invalid service, unable to load service file "{}.py"'.format(file_name)
            )
            raise e
        except OSError:
            if file_name.endswith(".py"):
                file_name = file_name[:-3]
            logging.getLogger("import").warning('Invalid service, no such service file "{}.py"'.format(file_name))
            sys.exit(2)
        except Exception as e:
            if file_name.endswith(".py"):
                file_name = file_name[:-3]
            logging.getLogger("import").warning('Unable to load service file "{}.py"'.format(file_name))
            logging.getLogger("import").warning("Error: {}".format(e))
            raise e
        return service_import

    @classmethod
    def import_module(cls, file_name: str) -> ModuleType:
        cwd = os.getcwd()
        file_path = "{}/{}".format(os.path.realpath(cwd), file_name)

        spec: Any = importlib.util.spec_from_file_location(file_name, file_path)
        module_import = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module_import)

        return module_import
