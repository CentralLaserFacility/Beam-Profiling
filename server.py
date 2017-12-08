from pcaspy import SimpleServer, Driver
from threading import Thread
import time, datetime
import numpy as np
      
prefix = 'DIP:PS:'
pvdb = {
    'TSTART' : { 'type' : 'int', 'value': 370 },
    'TEND'   : { 'type' : 'int', 'value': 780 },
    'NPOINT'   : { 'type' : 'int', 'value': 82 },
    'GAIN'  : { 'prec' : '2', 'value': 0.50 },
    'RESET'    : { 'type' : 'int'},
    'SCOPETRACE:GET'    : { 'type' : 'int'},
    'SCOPETRACE' : { 'prec' : 14, 'count' : 1000, 'value': 0.0},
    'WOBACKTRACE:GET'    : { 'type' : 'int'},
    'WOBACKTRACE' : { 'prec' : 14, 'count' : 1000, 'value': 0.0},
    'CLIPTRACE:GET'    : { 'type' : 'int'},
    'CLIPTRACE' : { 'prec' : 14, 'count' : 1000, 'value': 0.0},
    'CROPTRACE:GET'    : { 'type' : 'int'},
    'CROPTRACE' : { 'prec' : 14, 'count' : 1000, 'value': 0.0}
}

def timestamp():
    return str(datetime.datetime.utcnow())


class Shaping():


    def get_scope_trace(self):
        return np.loadtxt("./data/square_rounded__scope__i0")

    def get_woback_trace(self):
        return np.loadtxt("./data/square_rounded__woback__i0")

    def get_clip_trace(self):
        return np.loadtxt("./data/square_rounded__clip__i0")

    def get_crop_trace(self):
        return np.loadtxt("./data/square_rounded__crop__i0")



class SimpleDriver(Driver):

    def  __init__(self):
        super(SimpleDriver, self).__init__()
        self.busy = False
        self.updatePVs()

        self.shaping = Shaping()

    def reset_traces(self):
        self.setParam("SCOPETRACE",np.zeros(1000))
        self.setParam("WOBACKTRACE",np.zeros(1000))
        self.setParam("CLIPTRACE",np.zeros(1000))
        self.setParam("CROPTRACE",np.zeros(1000))

    def get_scope_trace(self):
        self.setParam("SCOPETRACE", self.shaping.get_scope_trace())
        
    def get_woback_trace(self):
        self.setParam("WOBACKTRACE", self.shaping.get_woback_trace())
    
    def get_clip_trace(self):
        self.setParam("CLIPTRACE", self.shaping.get_clip_trace())
    
    def get_crop_trace(self):
        self.setParam("CROPTRACE", self.shaping.get_crop_trace())
    
    def run_func_in_thread(self, function):
        self.busy = True
        function()
        self.updatePVs()
        self.busy = False


    def write(self, reason, value):
      
        print timestamp() + " | " + prefix + reason + " <-- " + str(value)

        if reason == 'RESET':
            if self.busy is False:
                t = Thread(target=self.run_func_in_thread, args=(self.reset_traces,))
                t.start()

        if reason == 'SCOPETRACE:GET':
            if self.busy is False:
                t = Thread(target=self.run_func_in_thread, args=(self.get_scope_trace,))
                t.start()

        if reason == 'WOBACKTRACE:GET':
            if self.busy is False:
                t = Thread(target=self.run_func_in_thread, args=(self.get_woback_trace,))
                t.start()

        if reason == 'CLIPTRACE:GET':
            if self.busy is False:
                t = Thread(target=self.run_func_in_thread, args=(self.get_clip_trace,))
                t.start()


        if reason == 'CROPTRACE:GET':
            if self.busy is False:
                t = Thread(target=self.run_func_in_thread, args=(self.get_crop_trace,))
                t.start()

        self.setParam(reason, value)
        return True
        

if __name__ == '__main__':

    server = SimpleServer()
    server.createPV(prefix, pvdb)
    print timestamp() + " | serving PVs: " + ' '.join([ prefix + key for key in pvdb.keys()])

    driver = SimpleDriver()
    while True: server.process(0.1)

