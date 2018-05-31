import matplotlib
matplotlib.use('WXAgg')
import numpy as np

from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigCanvas
from matplotlib.backends.backend_wx import NavigationToolbar2Wx
from matplotlib.figure import Figure
import pylab

import wx
from curve import Curve

#import locale
#locale.setlocale(locale.LC_ALL, 'C')


class GraphPanel(wx.Panel):

    def __init__(self,parent,curve):

        wx.Panel.__init__(self,parent)

        self._refreshTime = 500
        self._curve = curve
        self._data = curve.get_processed()
        
        self._init_plot()
        self._canvas = FigCanvas(self, -1, self._fig)
        
        self._vbox = wx.BoxSizer(wx.VERTICAL)
        self._vbox.Add(self._canvas, 1, flag=wx.LEFT | wx.TOP | wx.GROW)
        
        self.SetSizer(self._vbox)
        self._vbox.Fit(self)
        
        self._redraw_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_redraw_timer, self._redraw_timer)        
        self._redraw_timer.Start(self._refreshTime)
        
        
    def _init_plot(self):
        self._dpi = 100
        self._fig = Figure((3.0, 3.0), dpi=self._dpi)

        self._axes = self._fig.add_subplot(111)
        self._axes.set_title(self._curve.name())
        #self._axes.set_xlabel('Pixel', size=10)
        #self._axes.set_ylabel('Transmission', size = 10)

        pylab.setp(self._axes.get_xticklabels(), fontsize=8)
        pylab.setp(self._axes.get_yticklabels(), fontsize=8)
        
        self._plot_data = self._axes.plot(self._data)[0]    

                    
    def _draw_plot(self):
        #xdata = self._data[0]
        ydata = self._data

        #self.plot_data.set_xdata(xdata)
        self._plot_data.set_ydata(ydata)

        #xmin = np.min(xdata)
        #max = np.max(xdata)
        ymin = min(0.9*np.min(ydata),-0.05)
        ymax = max(1.1*np.max(ydata),1.05)
        

        #self._axes.set_xbound(lower=xmin, upper=xmax)
        self._axes.set_ybound(lower=ymin, upper=ymax)
       
        self._canvas.draw()
        
    
    def _on_redraw_timer(self,event):
        # Get new data and draw plot

        self._data = self._curve.get_processed()
        self._draw_plot()
    
    
class GraphFrame(wx.Frame):

    _title = 'AWG loop monitors'
    _maxRowSize = 4
    
    def __init__(self,curve_list):
        wx.Frame.__init__(self, None, -1, self._title)
        
        #curve_names = [str(i.name()) for i in curve_list]
        
        gridSizer = wx.GridBagSizer(hgap=3,vgap=3)
        
        for i in range(len(curve_list)):
            gridSizer.Add(GraphPanel(self,curve_list[i]), 
                pos=(i//self._maxRowSize, i%self._maxRowSize),
                flag = wx.GROW | wx.ALL)

        for i in range(min(len(curve_list),self._maxRowSize)):
            gridSizer.AddGrowableCol(i)

        for i in range(len(curve_list)//self._maxRowSize + 1):
                gridSizer.AddGrowableRow(i)
            
        
        self.SetSizerAndFit(gridSizer)
        

    def on_exit(self,event):
        self.Destroy()
        
if __name__ == "__main__":  

    bkg = Curve(curve_array = 0.3*np.ones(100), name='background')
    data = Curve()
    data.load(data='generateCurves/noisy.py')

    curve_list = [bkg,data,bkg,bkg,bkg,bkg]


    app = wx.App()
    app.frame = GraphFrame(curve_list)
    app.frame.Show()
    app.MainLoop()


