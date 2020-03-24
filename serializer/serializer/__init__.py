""" funcX : Fast function serving for clouds, clusters and supercomputers.

"""
import logging
from serializer.version import VERSION
from logging.handlers import RotatingFileHandler

__author__ = "The funcX team"
__version__ = VERSION


def set_file_logger(filename,
                    name='funcx.serializer',
                    level=logging.DEBUG,
                    maxBytes=32*1024*1024,
                    backupCount=1,
                    format_string=None):
    """Add a stream log handler.

    Args:
        - filename (string): Name of the file to write logs to
        - name (string): Logger name
        - level (logging.LEVEL): Set the logging level
        - maxBytes: The maximum bytes per logger file, default: 256MB
        - backupCount: The number of backup (must be non-zero) per logger file, default: 1
        - format_string (string): Set the format string

    Returns:
       -  None
    """
    if format_string is None:
        format_string = "%(asctime)s.%(msecs)03d %(name)s:%(lineno)d [%(levelname)s]  %(message)s"

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    handler = RotatingFileHandler(filename, maxBytes=maxBytes, backupCount=backupCount)
    handler.setLevel(level)
    formatter = logging.Formatter(format_string, datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def set_stream_logger(name='serializer', level=logging.DEBUG, format_string=None):
    """Add a stream log handler.

    Args:
         - name (string) : Set the logger name.
         - level (logging.LEVEL) : Set to logging.DEBUG by default.
         - format_string (string) : Set to None by default.

    Returns:
         - None
    """
    if format_string is None:
        # format_string = "%(asctime)s %(name)s [%(levelname)s] Thread:%(thread)d %(message)s"
        format_string = "%(asctime)s %(name)s:%(lineno)d [%(levelname)s]  %(message)s"

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setLevel(level)
    formatter = logging.Formatter(format_string, datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


logging.getLogger('serializer').addHandler(logging.NullHandler())
