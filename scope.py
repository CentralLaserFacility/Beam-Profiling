import visa
import time


class Scope(object):
    """ Scope instrument """

    def __init__(self, address, channel):

        self.wfm = []
        self.fileCnt = 0

        #pulse
        #self.pulseStart = 0 #s
        #self.pulseStop = 1.2e-008 # 12ns
        #self.startSample = 560
        #self.stopSample = 1040
        self.pulse = []

        # communication settings
        #self.rm = visa.ResourceManager("")  # use when using native NI library
        self.rm = visa.ResourceManager("@py")  # use when using python reimplentation of VISA

        self.c = self.rm.open_resource(address)
        self.c.read_termination = '\n'
        self.name = self.get('*IDN?')
        #self.c.write('*RST')
        self.set('FORMAT:DATA', 'REAL,32')                  # get the samples as float

        # channel settings
        # vertical scale channel 2: 0.02
        self.channelName = channel
        self.verticalScale = '0.04'
        self.skewTime = '2.325E-008'                             # skew offset 23.25ns
        self.set(self.channelName + ':SCAL' ,self.verticalScale)
        self.dataQueryCmd = self.channelName + ':WAV1:DATA?'
        self.set(self.channelName + ':SKEW:MAN'  ,'ON')          #enable skew
        self.set(self.channelName + ':SKEW:TIME' ,self.skewTime) #skew offset

        # trigger setup
        #self.triggerLevel = '1.5388'
        self.triggerLevel = '0.5'
        self.set('TRIG:SOUR',   'EXT')                      # enable external trigger
        self.set('TRIG:LEV5',   self.triggerLevel)          # set the level
        self.set('TRIG:MODE',   'NORMAL')

        # acquisiiton settings
        self.recordLength = '1600'
        self.timeScale = '4E-009'                           # 4ns/div
        self.referencePosition = '50'                       # defined in % of x axis
        self.referencePoint ='6E-009'                       # shifted from position. + mean to the left, - to the right
        self.nAverages = '20'
        self.resolution = self.get('ACQ:RES?')
        self.set('ACQ:POIN:AUTO', 'RECL')                   # set resolution dependency to record length
        self.set('ACQ:POIN',    self.recordLength)          # record length
        self.set('TIM:SCAL',    self.timeScale)             # time scale
        self.set('TIM:REF',     self.referencePosition)     # reference point
        self.set('TIM:HOR:POS', self.referencePoint)        # position
        time.sleep(0.1)

        self.set('ACQ:INT',  'SINX')                        # interpolation type: sinx/x
        self.set(self.channelName+'WAV:TYPE', 'SAMP')       # decimationmode: sample
        self.set(self.channelName+':ARIT', 'AVER')          # waveform arithmetic: average
        self.set('ACQ:COUN',    self.nAverages)             # number of averages


        print('Connected to: ' + self.name)

    def setPulse(self, startPulseTime, stopPulseTime):        # start and stop in s

        self.c.write('RUNS')
        self.wait()
        self.wfm = self.c.query_binary_values(self.dataQueryCmd, datatype='f')
        self.c.write('RUNS')
        self.wait()

        data = self.c.query(self.channelName+':WAV1:DATA:HEAD?')
        self.wait()
        print 'setpulse' + data
        xStart = data.split(',')[0]
        xStart = float(xStart)

        _startSample = abs(xStart - startPulseTime) / float(self.resolution)
        self.startSample = int(_startSample)

        _stopSample = abs(xStart - stopPulseTime) / float(self.resolution)
        self.stopSample = int(_stopSample)



    def set(self, cmd, arg):
        self.c.write(cmd + ' ' + arg)


    def get(self, cmd):
        ans = self.c.query(cmd)
        return ans


    def wait(self):
        ready = int(self.get('*OPC; *ESR?'))
        while not ready:
            time.sleep(0.001)
            ready = int(self.get('*OPC; *ESR?'))


    def fetch(self):
        self.c.write('RUNS')
        self.wait()

        self.wfm = self.c.query_binary_values(self.dataQueryCmd, datatype='f')

        self.pulse = self.wfm[self.startSample:self.stopSample]
        self.wait()
        print "Got pulse between: " + str(self.startSample) + " to " + str(self.stopSample)


    def saveWfm(self):
        filename = 'data/wfm' + str(self.fileCnt)
        with open(filename, 'w') as f:
            for n in self.wfm:
                f.write(str(n) + '\n')

        self.fileCnt += 1

    def savePulse(self):
        filename = 'data/pulse' + str(self.fileCnt)
        with open(filename, 'w') as f:
            for n in self.pulse:
                f.write(str(n) + '\n')

        self.fileCnt += 1


    def close(self):
        self.c.close()
