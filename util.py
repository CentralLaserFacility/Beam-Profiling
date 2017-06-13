import numpy as np
import csv
import matplotlib.pyplot as plt

def resample(data, npoints):

    im = np.arange(0,len(data))
    factor = len(data)/float(npoints)

    ip = np.arange(0, len(data), factor)
    p = np.interp(ip, im, data)

    return p

def normalise(data):
    return data/np.amax(data)

def clipnegative(data):
    return np.clip(data,0,np.amax(data))


def ramp(start, end, n_points):
    return np.linspace(start, end, n_points)

def zeros(n_points):
    return np.zeros(n_points)

def square(n_points):
    return np.ones(n_points)


def custom(f):
    return np.loadtxt(f)


def read_from_csv(filename):
    data = []
    f = open(filename, 'rt')
    try:
        reader = csv.reader(f,delimiter=';')
        for row in reader: data.append(float(row[0]))
        return data
    finally:
        f.close()

def save_to_txt(points, filename):
    f = open(filename, 'w')
    for point in points:
        f.write(str(point))
        f.write("\n")
    f.close()


def plotstart():
    plt.ion()

def plotend():
    plt.ioff()
    plt.show()

def plotclear():
    plt.clf()

def plot(data, point='*', linestyle='-', x=None):    
    plt.plot(data, point, linestyle=linestyle)

def plotx(x, data, point='*', linestyle='-'):    
    plt.plot(x,data, point, linestyle=linestyle)

def plotend():
    plt.ioff()
    plt.show()

def plotpause(data, clear=True):
    if clear: plotclear()
    plot(data)
    raw_input("continue")

    
