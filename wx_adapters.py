"""wx implementations of the hooks the core uses to report back to the GUI."""

import logging

import wx

MESSAGE_TIME_FORMAT = "%b_%d_%H:%M.%S"


class WxProgress:
    """Shows hardware progress (beam_shaper.core.interfaces.Progress) in a wx.ProgressDialog."""

    def __init__(self, parent):
        self.parent = parent
        self.dialog = None

    def start(self, title, message, maximum=None):
        self.dialog = wx.ProgressDialog(
            title, message, maximum or 100, parent=self.parent, style=wx.PD_AUTO_HIDE
        )

    def update(self, value, message):
        if value is None:
            self.dialog.Pulse(message)
        else:
            self.dialog.Update(value, message)

    def finish(self):
        if self.dialog:
            self.dialog.Destroy()
            self.dialog = None


class TextCtrlLogHandler(logging.Handler):
    """Sends log records to a read-only wx.TextCtrl."""

    def __init__(self, text_ctrl):
        logging.Handler.__init__(self)
        self.text_ctrl = text_ctrl
        self.setFormatter(logging.Formatter("%(asctime)s: %(message)s", MESSAGE_TIME_FORMAT))

    def emit(self, record):
        line = self.format(record) + "\n"
        if wx.IsMainThread():
            self.text_ctrl.WriteText(line)
        else:
            wx.CallAfter(self.text_ctrl.WriteText, line)
