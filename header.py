#########################################################################################
# Any constants that are needed and utility functions
#########################################################################################

from datetime import datetime
import sys, os, wx, enum

if sys.version_info[0] < 3:
    import ConfigParser as cp
else:
    import configparser as cp
    
config = cp.RawConfigParser()

config.read('./config.ini')


SCOPE_WAIT_TIME = config.getfloat('timing', 'scope_wait')
SIMULATION = config.getboolean('sim','sim')
DIAG_FILE_LOCATION = config.get('file_locations','diag')
AWG_PREFIX = config.get('pvs','awg_prefix')
DEFAULT_SCOPE_PV = config.get('pvs','scope')
PAUSE_BETWEEN_AWG_WRITE = config.getfloat('timing','awg_wait')
LIBRARY_FILES_LOCATION = config.get('file_locations','curve')
AWG_ZERO_SHIFT = config.getfloat('awg', 'awg_zero_shift')
AWG_NS_PER_POINT = config.getfloat('awg', 'awg_ns_per_point')
AWG_WRITE_METHOD = config.get('awg', 'awg_write_method')
PULSE_PEAK_POWER = config.getfloat('safety', 'pulse_peak_power')
AUTO_LOOP = config.getboolean('safety', 'auto_loop')
AUTO_LOOP_WAIT = config.getfloat('safety', 'auto_loop_wait')

EPICS_CA_ADDR_LIST = config.get('epics', 'epics_ca_addr_list')
EPICS_CA_AUTO_ADDR_LIST = config.get('epics', 'epics_ca_auto_addr_list')


# Set environment variables for EPICS
def epics_setup(epicsCAAddrList, epicsCAAutoAddrList):
    os.environ["EPICS_CA_ADDR_LIST"] = epicsCAAddrList
    os.environ["EPICS_CA_AUTO_ADDR_LIST"] = epicsCAAutoAddrList
    

# Provides a date and time string for messages printed to the console
def get_message_time():
    return datetime.now().strftime("%b_%d_%H:%M.%S")+": "

# Holds utility constants
class CODES():
    Proceed = 1 
    Recalc = 2
    Abort = 3 
    Error = 4 
    NoError = 5
