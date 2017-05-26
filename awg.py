from epics import caget, caput


class  Awg(object):

    def __init__(self):
        self.name = 'AWG:'
        self.start = 0.0
        self.width = 0.125
        self.maxIncrement = 1.0
        self.waveform = []




    def tweak(self):
        for sample in self.waveform:
            