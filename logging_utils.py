import os
import traceback

import logging
import logging.config

from SGDPyUtil.singleton_utils import SingletonInstance
from SGDPyUtil.main import get_data_path

is_kiwoom_process = False


def propagate_is_kiwoom_process(value):
    """propgate the variable[is_kiwoom_process]"""
    global is_kiwoom_process
    is_kiwoom_process = value
    return


class Logger(SingletonInstance):
    def __init__(self, *args, **kwargs):
        global is_kiwoom_process

        # define prefix_name and log_type
        prefix_name = ""
        log_type = "log03"

        # if we're running is_kiwoom_proces, set different properties
        if is_kiwoom_process:
            prefix_name = "[kiwoom]"
            log_type = "log02"

        # set prefix
        self.prefix = prefix_name

        # init logging config file and create new instance for logger
        self.init_settings(log_type)

        return

    def init_settings(self, log_type):
        try:
            # get the logging config file
            conf_path = os.path.join(
                get_data_path(), "SGDPyUtil", ".conf", "logging.conf"
            )

            # only enable file logging when log03 type is specified
            if log_type == "log03":
                logging_file_name = "SGDTradeFramework.log"
                logging.config.fileConfig(
                    conf_path,
                    disable_existing_loggers=False,
                    defaults={"str_log_file_name": logging_file_name},
                )

            self.logger = logging.getLogger(log_type)
        except:
            print(
                f"[ERROR] failed to initialize Logger instance: {traceback.format_exc()}"
            )
        return

    def info(self, message):
        # composite message
        composite_message = self.prefix + message

        # logging
        self.logger.info(composite_message)
        return


def logging_func(desc=""):
    """
    logging delegate for function
    """

    def decorator(function):
        def wrapper(*args, **kwargs):

            # mark start to execute function
            Logger.instance().info(f"[logging_func][start] {function.__name__}")

            # if any desc is exists, log the description
            if desc is not "":
                Logger.instance().info(f"[logging_func][desc] {desc}")

            # execute function
            result = function(*args, **kwargs)

            # mark start to execute function
            Logger.instance().info(f"[logging_func][end] {function.__name__}")

            return result

        return wrapper

    return decorator
