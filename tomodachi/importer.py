import os
import sys
import logging
import importlib
import importlib.util
from types import ModuleType
from typing import Any  # noqa


class ServiceImporter(object):
    @classmethod
    def import_service_file(cls, file_name: str) -> ModuleType:
        cwd = os.getcwd()
        file_path = '{}/{}.py'.format(os.path.realpath(cwd), file_name)
        try:
            spec = importlib.util.spec_from_file_location(file_name, file_path)  # type: Any
            service_import = importlib.util.module_from_spec(spec)
            try:
                importlib.reload(service_import)
                service_import = importlib.util.module_from_spec(spec)
            except ImportError:
                pass
            sys.path.insert(0, cwd)
            sys.path.insert(0, os.path.dirname(file_path))
            spec.loader.exec_module(service_import)
        except ImportError as e:
            if file_name.endswith('.py'):
                return cls.import_service_file(file_name[:-3])
            logging.getLogger('import').warning('Invalid service, unable to load service file "{}"'.format(file_name))
            raise e
        except OSError:
            if file_name.endswith('.py'):
                return cls.import_service_file(file_name[:-3])
            logging.getLogger('import').warning('Invalid service, no such service file "{}"'.format(file_name))
            sys.exit(2)
        except Exception as e:
            logging.getLogger('import').warning('Unable to load service file "{}"'.format(file_name))
            logging.getLogger('import').warning('Error: {}'.format(e))
            raise e
        return service_import
