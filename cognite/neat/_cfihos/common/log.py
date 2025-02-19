import logging
import sys


def log_level_converter(log_level):
    convert_dict = {
        "debug": 10,
        "info": 20,
        "warning": 30,
        "error": 40,
        "d": 10,
        "i": 20,
        "w": 30,
        "e": 40,
    }

    return convert_dict[log_level]


def log_init(processor_path: str, log_level: str) -> logging.Logger:
    logger = logging.getLogger(processor_path)
    logger.setLevel(level=log_level_converter(log_level.lower()))
    log_handler = logging.StreamHandler(sys.stdout)
    log_formatter = logging.Formatter("%(asctime)s %(name)-12s %(levelname)-8s %(processName)s %(lineno)s %(message)s")
    log_handler.setFormatter(log_formatter)
    logger.addHandler(log_handler)
    return logger
