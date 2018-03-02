import logging
from logging.handlers import WatchedFileHandler
from typing import Optional, Union, Any


def log_setup(service: Any, name: Optional[str]=None, level: Optional[Union[str, int]]=None, formatter: Optional[Union[logging.Formatter, str, bool]]=True, filename: Optional[str]=None) -> logging.Logger:
    if not name:
        name = 'log.{}'.format(service.name)
    if not filename:
        raise Exception('log_filename must be specified for logging setup')

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if level and type(level) is str:
        level = getattr(logging, str(level))

    if not [x for x in logger.handlers if isinstance(x, WatchedFileHandler) and (level is None or level == x.level)]:
        try:
            wfh = WatchedFileHandler(filename=filename)
        except FileNotFoundError as e:
            logging.getLogger('logging').warning('Unable to use file for logging - invalid path ("{}")'.format(filename))
            raise e
        except PermissionError as e:
            logging.getLogger('logging').warning('Unable to use file for logging - invalid permissions ("{}")'.format(filename))
            raise e

        if level:
            wfh.setLevel(level)

        if formatter and type(formatter) is str:
            formatter = logging.Formatter(str(formatter))
        if formatter and type(formatter) is bool and formatter is True:
            formatter = logging.Formatter('%(asctime)s (%(name)s): %(message)s')

        if formatter and isinstance(formatter, logging.Formatter):
            wfh.setFormatter(formatter)

        logger.addHandler(wfh)

    return logger


def log(service: Any, *args: Any, **kwargs: Any) -> None:
    log_name = 'log.{}'.format(service.name)
    log_level = None
    log_message = None
    if len(args) == 1:
        log_message = args[0]
    if len(args) == 2:
        if type(args[0]) is int:
            log_level = args[0]
        else:
            log_name = args[0]
        log_message = args[1]
    if len(args) == 3:
        log_name = args[0]
        log_level = int(args[1]) if type(args[1]) is int else getattr(logging, str(args[1]))
        log_message = args[2]

    if kwargs.get('level'):
        log_level = 0
        log_level_value = kwargs.pop('level', 0)
        if type(log_level_value) is int:
            log_level = int(log_level_value)
        else:
            log_level = int(getattr(logging, str(log_level_value)))
    if kwargs.get('name'):
        log_name = kwargs.pop('name', None)
    if kwargs.get('msg'):
        log_message = kwargs.pop('msg', None)
    if kwargs.get('message'):
        log_message = kwargs.pop('message', None)

    if not log_level:
        log_level = logging.INFO

    logger = logging.getLogger(log_name)

    if log_message:
        logger.log(level=log_level, msg=str(log_message), **kwargs)
