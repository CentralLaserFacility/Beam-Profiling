import epics
from epics.wx import EpicsFunction, DelayedEpicsCallback
import wx
import datetime



class pvSwitch(wx.Panel):
    """ A boolean switch for a user defined PV """
    def __init__(self,parent):

        txtBoxSize = (200,25)

        wx.Panel.__init__(self,parent)

        # Create the sizer
        gridSizer = wx.GridBagSizer(hgap=3,vgap=0)

        # Setup the controls
        self.pvNameLabel = wx.StaticText(self, label="PV Name")
        self.onOffLabel  = wx.StaticText(self, label="On/Off")
        self.pvNameBox   = wx.TextCtrl(self, size = txtBoxSize, style=wx.TE_PROCESS_ENTER)
        self.onOffButton = epics.wx.PVCheckBox(self)

        # Add the controls to the sizer
        gridSizer.Add(self.pvNameLabel, pos=(0,0))
        gridSizer.Add(self.onOffLabel, pos=(0,1))
        gridSizer.Add(self.pvNameBox, pos=(1,0))
        gridSizer.Add(self.onOffButton, pos=(1,1))

        # Bind the callback functions
        self.pvNameBox.Bind(wx.EVT_CHAR, self.onNameBox)

        self.SetSizerAndFit(gridSizer)

    #@EpicsFunction
    def onNameBox(self,event):
        """ Connects to the PV when the user hits enter """
        if event.GetKeyCode() == wx.WXK_RETURN:
            self.pvname = self.pvNameBox.GetValue().strip()
            self.pv = epics.PV(self.pvname, connection_callback=self.onConnect)
            #Change the colour after connection attempt, and set the on/off pv
            #self.onOffButton.SetPV(pv=self.pvname)
            if self.pv.connected:
                self.pvNameBox.SetBackgroundColour('Green')
            else:
                self.pvNameBox.SetBackgroundColour('Red')
            self.pvNameBox.Refresh()
        event.Skip()

    @DelayedEpicsCallback
    def onConnect(self, **kwargs):
        """ Change the colour of the field to reflect connetion status """
        if self.pv.connected:
            self.pvNameBox.SetBackgroundColour('Green')
            #Associate the correct pv with the checkbox if connection is successful
            self.onOffButton.SetPV(pv=self.pv)
        else:
            self.pvNameBox.SetBackgroundColour('Red')
        self.pvNameBox.Refresh()


class FileLine(wx.Panel):
    def __init__(self,parent,text = ['File type', 'Load file type']):

        txtBoxSize = (600,40)

        wx.Panel.__init__(self,parent)

        sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.file_name_text = wx.TextCtrl(self, size = txtBoxSize, value = text[0])
        self.file_load_button = wx.Button(self, label = text[1]) 

        sizer.Add(self.file_name_text,0,0,0)
        sizer.Add(self.file_load_button,0,0,0)

        self.file_load_button.Bind(wx.EVT_BUTTON, self.on_browse)

        self.SetSizerAndFit(sizer)

    def on_browse(self, event):
        frame = wx.Frame(None, -1, "Load a curve")
        frame.SetDimensions(0,0,200,50)

        with wx.FileDialog(frame, "Load Curve", 
                        style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return    # Quit with no file loaded

            pathname = fileDialog.GetPath()
        
        self.file_name_text.SetValue(pathname)
        






app = wx.App(False)
frame = wx.Frame(None)


numPanels = 3
vBoxSizer = wx.BoxSizer(wx.VERTICAL)

panels=[]
for i in range(numPanels):
    vBoxSizer.Add(FileLine(frame, ['Background file path', 'Choose bkg']))


frame.SetSizerAndFit(vBoxSizer)

frame.Show()
app.MainLoop()
