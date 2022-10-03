import wx, sys, os, epics


if sys.version_info[0] < 3:
    import ConfigParser as cp
else:
    import configparser as cp
    config = cp.RawConfigParser()
    
class Configuration(wx.Dialog):
    """
    Hold details of the configuration held in the config file, in addition to user defined configurations
    at run time. Provide a GUI to set the values in the configuration file. 
    """
    
    def __init__(self, *args, **kwds):
        
        wx.Dialog.__init__(self, *args, **kwds)
        self.SetTitle("Beam profiling configuration")

        # Set all the configurable parameters
        self.parms = {}
        self.parms["diag"] = Param(label = "Diagnostic files location", widget = wx.TextCtrl(self), section = "file_locations")
        self.parms["curve"] = Param(label = "Library files location", widget = wx.TextCtrl(self), section = "file_locations")
        self.parms["filter"] = Param(label = "Filter file", widget = wx.TextCtrl(self), section = "file_locations")
        self.parms["pulse_peak_power"] = Param(kind = "float", label = "Peak Power", widget = wx.TextCtrl(self), section = "safety")
        self.parms["auto_loop"] = Param(kind = "bool", label = "Auto loop", widget = wx.CheckBox(self), section = "safety")
        self.parms["auto_loop_wait"] = Param(kind = "float", label = "Auto loop wait (s)", widget = wx.TextCtrl(self), section = "timing")
        self.parms["scope_wait"] = Param(kind = "float", label = "Scope read wait (s)", widget = wx.TextCtrl(self), section = "timing")
        self.parms["awg_wait"] = Param(kind = "float", label = "AWG write wait (s)", widget = wx.TextCtrl(self), section = "timing")
        self.parms["scope"] = Param(label = "Default scope PV", widget = wx.TextCtrl(self), section = "pvs")
        self.parms["awg_prefix"] = Param(label = "AWG_PV prefix", widget = wx.TextCtrl(self), section = "pvs")
        self.parms["sim"] = Param(kind = "bool", label = "Simulation", widget = wx.CheckBox(self), section = "sim")
        self.parms["awg_zero_shift"] = Param(kind = "float", label = "AWG zero shift", widget = wx.TextCtrl(self), section = "awg")
        self.parms["noise_threshold_percentage"] = Param(kind = "float", label = "Noise threshold (%)", widget = wx.TextCtrl(self), section = "awg")
        self.parms["awg_ns_per_point"] = Param(kind = "float", label = "AWG calib (ns/point)", widget = wx.TextCtrl(self), section = "awg")
        self.parms["awg_write_method"] = Param(label = "AWG write method", widget = wx.ComboBox(self, choices=['pts', 'wfm'], style=wx.CB_READONLY), section = "awg")
        self.parms["epics_ca_addr_list"] = Param(label = "Channel Access addr list", widget = wx.TextCtrl(self), section = "epics")
        self.parms["epics_ca_auto_addr_list"] = Param(label = "Channel Access auto addr list", widget = wx.ComboBox(self, choices=['No', 'Yes'], style=wx.CB_READONLY), section = "epics")



        # UI elements
        self.font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD, 0, "")
        self.okButton = wx.Button(self, label="Apply")
        self.cancelButton = wx.Button(self, label="Cancel")
        self.buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.buttonSizer.Add(self.okButton)
        self.buttonSizer.Add(self.cancelButton)
        self.szr = wx.GridBagSizer()

        # Bindings
        self.okButton.Bind(wx.EVT_BUTTON, self.onApply)
        self.cancelButton.Bind(wx.EVT_BUTTON, self.onQuit)
        self.Bind(wx.EVT_CLOSE, self.onQuit)
           
        # Read in the parameters
        self.readConfig()
        
        self.perform_setup()

        # Build the interface
        self.__do_layout()

    def onQuit(self, evt):
        self.EndModal(0)

    def onApply(self, evt):
        self.writeConfig()
        self.perform_setup() 
        self.EndModal(1)
        
    def perform_setup(self):
        # Do any setup needed after a change in configuration 
        self.epics_setup()
        self.create_diag_folder()

    def getVal(self, k):
        if k in self.parms.keys():
            return self.parms[k].value
        else:
            return None
    
    def setVal(self, k, value, kind = "udf"):
        if k in self.parms.keys():
            self.parms[k].value = value
        else:
            self.parms[k] = Param(value = value, kind = kind)

    def readConfig(self, filename='./config.ini'):
        config.read(filename)

        for name, parm in self.parms.items():
            # Add special handling if the parameter kind needs it
            if parm.kind == "bool":
                parm.value = config.getboolean(parm.section, name)
                parm.widget.SetValue(parm.value)
            elif parm.kind == "float":     
                parm.value = config.getfloat(parm.section, name)   
                parm.widget.SetValue(str(parm.value))
            else:
                parm.value = config.get(parm.section, name)
                parm.widget.SetValue(parm.value) 


    def writeConfig(self, filename='./config.ini'):
        
        for name, parm in self.parms.items():
            # Only write out parameters destined for the config file
            if not parm.section: continue 
            value = parm.widget.GetValue()
            config.set(parm.section, name, value)
            # Set the latest values in the parms dictionary
            if parm.kind == "bool":
                parm.value = bool(value)
            elif parm.kind == "float":     
                parm.value = float(value)
            else:
                parm.value = value

        
        with open(filename, 'w') as configfile:
            config.write(configfile)


    # Set environment variables for EPICS
    def epics_setup(self):
        os.environ["EPICS_CA_ADDR_LIST"] = self.parms['epics_ca_addr_list'].value
        os.environ["EPICS_CA_AUTO_ADDR_LIST"] = self.parms['epics_ca_auto_addr_list'].value
        # Add caRepeater to the path. The epics module does the hard work of finding
        # ca.dll and caRepeater is in the same dir
        try:
            ca_dir = epics.ca._find_lib('ca.dll')[:-6]
        except epics.ca.ChannelAccessException:
            # Can't find library path. Try another way
            ca_dir = epics.__path__[0] + os.path.sep + sys.platform
        if ca_dir not in(sys.path):
            sys.path.append(ca_dir)

    # Create folder for diagnostic files if necessary
    def create_diag_folder(self):
        if not os.path.exists(self.parms['diag'].value):
            os.makedirs(self.parms['diag'].value)


    def __do_layout(self):
        width = 30
        i=0   
        for parm in self.parms.values():
            # Only set out widgets for those parms that are set via the config panel
            if parm.widget:
                label = wx.StaticText(self, label = parm.label)
                self.szr.Add(label, pos = (i,0), span = (1,1), flag = wx.EXPAND|wx.ALL, border = 5)
                self.szr.Add(parm.widget, pos = (i,1), span = (1,width), flag = wx.EXPAND|wx.ALL, border = 5)
                label.SetFont(self.font)
                i+=1

        self.szr.Add(self.buttonSizer, pos=(i,width), flag = wx.EXPAND|wx.ALL, border = 5)
        self.SetSizerAndFit(self.szr)
        self.Layout()

        

class Param():
    """
    Class to hold the configurable parameters. 
        kind: type of parameter in case it needs special handling. This is just a string you use to identify those parms, 
            it doesn't need to represent a python type
        label: a string for the label widget for those parms that will be set via the config panel
        widget: the widget that will display in the config panel for parms that appear there
        section: the section of the config file that holds the parms, for those that appear there
        value: the current value of the parameter
    """
    def __init__(self, kind="string", label="", widget = None, section = None, value = None):
        self.kind = kind
        self.label = label
        self.widget = widget
        self.section = section
        self.value = value


if __name__ == "__main__":
    app = wx.App()
    
    dlg = Configuration(None)
    dlg.ShowModal()

    #dlg.readConfig()
    #print(dlg.parms['diag'].value, dlg.parms['sim'].value==True)
    #for name, parm in dlg.parms.items():
    #    print(name, parm.value)