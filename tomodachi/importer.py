import os
import sys
import logging
import importlib.util


class ServiceImporter(object):
    @classmethod
    def import_service_file(cls, file_name):
        file_path = '{}/{}.py'.format(os.path.dirname(os.path.realpath(sys.argv[0])), file_name.replace('.', '/'))
        try:
            spec = importlib.util.spec_from_file_location(file_name, file_path)
            service_import = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(service_import)
        except ImportError as e:
            if file_name.endswith('.py'):
                return cls.import_service_file(file_name[:-3])
            logging.getLogger('import').warn('Invalid service, unable to load service file "{}"'.format(file_name))
            raise e
            sys.exit(2)
        except OSError:
            if file_name.endswith('.py'):
                return cls.import_service_file(file_name[:-3])
            logging.getLogger('import').warn('Invalid service, no such service file "{}"'.format(file_name))
            sys.exit(2)
        except Exception as e:
            logging.getLogger('import').warn('Unable to load service file "{}"'.format(file_name))
            logging.getLogger('import').warn('Error: {}'.format(e))
            raise e
            sys.exit(2)
        return service_import
