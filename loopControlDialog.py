import wx
from util import CODES

class LoopControlDialog(wx.Dialog):
    def __init__(self, parent, title = "Message"):
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title)

        self.gain = 0.5
        self.gainLabel = wx.StaticText(self, label="Gain?")
        self.gainTxtCtrl = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER, value = str(self.gain))
        self.applyButton = wx.Button(self, label = "Apply")
        self.recalcButton = wx.Button(self, label = "Replot")
        self.pauseButton = wx.Button(self, label = "Pause")

        self.gainTxtCtrl.Bind(wx.EVT_TEXT_ENTER, self.onGainChange)
        self.gainTxtCtrl.Bind(wx.EVT_KILL_FOCUS, self.onGainChange)
        self.applyButton.Bind(wx.EVT_BUTTON, self.onApply)
        self.recalcButton.Bind(wx.EVT_BUTTON, self.onRecalc)
        self.pauseButton.Bind(wx.EVT_BUTTON, self.onPause)
        self.Bind(wx.EVT_CLOSE, self.onQuit)

        szr = wx.GridBagSizer()
        szr.Add(self.gainLabel, pos = (0, 0), span = (1, 2), flag = wx.EXPAND|wx.ALL, border = 5)
        szr.Add(self.gainTxtCtrl, pos = (1,0), span = (1,3), flag = wx.EXPAND|wx.ALL, border = 5)
        szr.Add(self.applyButton, pos = (2,0), span = (1,1), flag = wx.EXPAND|wx.ALL, border = 5)
        szr.Add(self.recalcButton, pos = (2,1), span = (1,1), flag = wx.EXPAND|wx.ALL, border = 5)
        szr.Add(self.pauseButton, pos = (2,2), span = (1,1), flag = wx.EXPAND|wx.ALL, border = 5)
        self.SetSizerAndFit(szr)

    def onGainChange(self, evt):
        current_gain = self.gain
        try:
            gain = float(self.gainTxtCtrl.GetValue())
        except:
            gain = self.gain
        self.gain = max(0, min(gain,1))
        self.gainTxtCtrl.SetValue(str(self.gain))
        if self.gain != current_gain:
            #self.applyButton.Disable()
            self.EndModal(CODES.Recalc)
        evt.Skip()

    def onRecalc(self, evt):
        #self.applyButton.Enable()
        self.EndModal(CODES.Recalc)
    
    def onApply(self, evt):
        self.EndModal(CODES.Proceed)
    
    def onPause(self, evt):
        self.EndModal(CODES.Pause)
    
    def onQuit(self, evt):
        self.EndModal(CODES.Abort)

    def SetValue(self, value):
        try:
            self.gain = float(value)
            self.gainTxtCtrl.SetValue(value)
        except:
            pass
    
    def GetValue(self):
        return self.gainTxtCtrl.GetValue()



if __name__ == "__main__":

    app = wx.App()
    dlg = LoopControlDialog(None)
    dlg.SetValue("0.2")
    if dlg.ShowModal() == 2:
        print(dlg.GetValue())
