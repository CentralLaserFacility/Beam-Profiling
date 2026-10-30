import wx

from beam_shaper.core.config import AppConfig


class ConfigDialog(wx.Dialog):
    """Edits an AppConfig. On Apply the config is updated and saved to filename."""

    def __init__(self, parent, config, filename="./config.ini"):
        wx.Dialog.__init__(self, parent)
        self.SetTitle("Beam profiling configuration")
        self.config = config
        self.filename = filename

        # One widget per config option, chosen by the option's type
        self.widgets = {}
        for option in AppConfig.options():
            choices = option.metadata["choices"]
            if option.type is bool:
                widget = wx.CheckBox(self)
            elif choices:
                widget = wx.ComboBox(self, choices=list(choices), style=wx.CB_READONLY)
            else:
                widget = wx.TextCtrl(self)
            self.widgets[option.name] = widget

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

        self.__do_layout()

    def ShowModal(self):
        # Always start from the current config, discarding any cancelled edits
        for name, widget in self.widgets.items():
            value = getattr(self.config, name)
            widget.SetValue(value if isinstance(value, bool) else str(value))
        return wx.Dialog.ShowModal(self)

    def onQuit(self, evt):
        self.EndModal(0)

    def onApply(self, evt):
        edited = AppConfig(**vars(self.config))
        try:
            for name, widget in self.widgets.items():
                edited.set_from_string(name, widget.GetValue())
        except ValueError as e:
            label = next(o.metadata["label"] for o in AppConfig.options() if o.name == name)
            wx.MessageDialog(
                self, "{0}: {1}".format(label, e), "Invalid value", style=wx.ICON_ERROR
            ).ShowModal()
            return
        vars(self.config).update(vars(edited))
        self.config.save(self.filename)
        self.config.ensure_diag_folder()
        self.EndModal(1)

    def __do_layout(self):
        width = 30
        i = 0
        for option in AppConfig.options():
            label = wx.StaticText(self, label=option.metadata["label"])
            self.szr.Add(label, pos=(i, 0), span=(1, 1), flag=wx.EXPAND | wx.ALL, border=5)
            self.szr.Add(
                self.widgets[option.name],
                pos=(i, 1),
                span=(1, width),
                flag=wx.EXPAND | wx.ALL,
                border=5,
            )
            label.SetFont(self.font)
            i += 1

        self.szr.Add(self.buttonSizer, pos=(i, width), flag=wx.EXPAND | wx.ALL, border=5)
        self.SetSizerAndFit(self.szr)
        self.Layout()


if __name__ == "__main__":
    app = wx.App()
    dlg = ConfigDialog(None, AppConfig.load())
    dlg.ShowModal()
