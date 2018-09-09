#########################################################################################
# Any constants that are needed and utility functions
#########################################################################################


import configparser
from datetime import datetime

config = configparser.RawConfigParser()
config.read('./config.ini')


SCOPE_WAIT_TIME = config.getfloat('timing', 'scope_wait')
SIMULATION = config.getboolean('sim','sim')
DIAG_FILE_LOCATION = config.get('file_locations','diag')
AWG_PREFIX = config.get('pvs','awg_prefix')
DEFAULT_SCOPE_PV = config.get('pvs','scope')
PAUSE_BETWEEN_AWG_WRITE = config.getfloat('timing','scope_wait')
LIBRARY_FILES_LOCATION = config.get('file_locations','curve')
NO_ERR = config.getint('util','no_err')
AWG_ZERO_SHIFT = config.getfloat('util', 'awg_zero_shift')


def get_message_time():
    return datetime.now().strftime("%b_%d_%H:%M.%S")+": "