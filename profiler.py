import sys
import os
import numpy as np
from scope import Scope




def run():
    while True:
        scope.fetch()
        scope.savePulse()


if __name__ == '__main__':
    try:
        scope = Scope('TCPIP::192.168.41.52::5025::SOCKET', 'chan1')
        scope.setPulse(2e-9, 1.2e-8)
        run()
    except KeyboardInterrupt:
        print 'Interrupted'
        try:
            scope.close()
            sys.exit(0)
        except SystemExit:
            os._exit(0)
