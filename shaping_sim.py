import util
import sys
import numpy as np
from curve import Curve
import matplotlib.pyplot as plt
import time

#Do some setup

bkg_trace = Curve()
start_trace = Curve()


#start with a square trace at the output
target_trace = Curve(curve_array=util.square(82))

bkg_trace.load(num_points=82, trim_method='resample')
start_trace.load(num_points=82, trim_method='resample')

plt.figure("Check the input data")

bkg_trace.plot_processed('r')
start_trace.process(bkg = bkg_trace)
start_trace.plot_raw('b--')
start_trace.plot_processed('b-')
target_trace.plot_processed('g')

target = target_trace.get_raw() 



gain = 0.3
i=0
initial = current = start_trace.get_processed() + 0.01

while i < 20:
    plt.figure("Correction factor to be applied")
    plt.show(block=False) 

    correction_factor = np.nan_to_num(target/current)
    correction_factor = (correction_factor - 1) * gain + 1

    plt.plot(correction_factor)

    current = current * correction_factor

    plt.figure("New output and target")
    plt.show(block=False)
    plt.plot(current)
    plt.plot(target)
    plt.plot(initial)


    raw_input('Any key to continue')
    


    i+=1