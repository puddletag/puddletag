import logging
import logging.config

from .constants import LOG_FILENAME


def init_logger(level):
    config = {
        "version": 1,
        "formatters": {
            "simple": {
                "format": '[%(asctime)s]%(levelname)s:%(message)s',
            }
        },
        "handlers": {
            "console": {
                "class": 'logging.StreamHandler',
                "level": level if level == logging.DEBUG else logging.ERROR,
                "formatter": 'simple',
                "stream": 'ext://sys.stdout',
            },
            "file": {
                "class": 'logging.handlers.RotatingFileHandler',
                "level": level,
                "formatter": 'simple',
                'filename': LOG_FILENAME,
                'maxBytes': 1024 * 1024 * 10  # 10MB
            }
        },
        "root": {
            "level": level,
            "handlers": ['file', 'console'],
        }
    }
    logging.config.dictConfig(config)
