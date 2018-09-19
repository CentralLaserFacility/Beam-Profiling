#########################################################################################
#Any constants that are needed
# SCOPE_WAIT_TIME = 2.1 # Seconds to wait for a caget from the scope to return
# SIMULATION = False
# DIAG_FILE_LOCATION = "./diag_files/"
# AWG_PREFIX = "AWG"
# DEFAULT_SCOPE_PV="CO-SCOPE-2:CH2:ReadWaveform"
# PAUSE_BETWEEN_AWG_WRITE = 0.3
# LIBRARY_FILES_LOCATION = "./curve_library/"
# NO_ERR = 0
#########################################################################################


import configparser

config = configparser.RawConfigParser()
config.read('./config.ini')


SCOPE_WAIT_TIME = config.getfloat('timing', 'scope_wait')
SIMULATION = config.getboolean('sim','sim')
DIAG_FILE_LOCATION = config.get('file_locations','diag')
AWG_PREFIX = config.get('pvs','awg')
DEFAULT_SCOPE_PV = config.get('pvs','scope')
PAUSE_BETWEEN_AWG_WRITE = config.getfloat('timing','scope_wait')
LIBRARY_FILES_LOCATION = config.get('file_locations','curve')
NO_ERR = config.getint('util','no_err')

