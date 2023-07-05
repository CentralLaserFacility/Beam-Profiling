import wx, os, wx.stc, keyword

class FileEditDialog(wx.Dialog):
    
    def __init__(self, parent, filename, *args, **kwargs):

        style =  wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER 
        wx.Dialog.__init__(self, None, title=filename, style=style)
             
        editorWindow = wx.stc.StyledTextCtrl(self, style=wx.TE_PROCESS_TAB|wx.TE_MULTILINE| wx.TE_DONTWRAP)
        editorWindow.SetInitialSize((800, 800))
        editorWindow.SetLexer(wx.stc.STC_LEX_PYTHON)
        keywords = self.getKeyWords() 
        editorWindow.SetKeyWords(0, keywords)
   
        buttons = self.CreateButtonSizer(wx.OK|wx.CANCEL)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(editorWindow, 1, wx.EXPAND|wx.ALL, 5)
        sizer.Add(buttons, 0, wx.EXPAND|wx.ALL, 5)
        self.SetSizerAndFit(sizer)
            
        self.editorWindow = editorWindow
        self.setupSyntaxHighlighting()
        self.filename = filename 
        self.getFile()
        self.Bind(wx.EVT_BUTTON, self.onOk, id=wx.ID_OK) 
        self.Bind(wx.EVT_BUTTON, self.onCancel, id=wx.ID_CANCEL) 
    

    def onOk(self, evt):
        with open(self.filename,'w') as f:
            f.write(self.editorWindow.GetValue())      
        self.EndModal(1)
    

    def onCancel(self, evt):
        self.EndModal(0)
    

    def getKeyWords(self):
        kws = ""
        for k in keyword.kwlist:
            kws += k+" "
        return kws


    def getFile(self):
        with open(self.filename,'r') as f:
            file_text = f.read()        
            self.editorWindow.SetValue(file_text)


    def setupSyntaxHighlighting(self):
        faces = { 'times': 'Times',
                      'mono' : 'Courier',
                      'helv' : 'Helvetica',
                      'other': 'new century schoolbook',
                      'size' : 12,
                      'size2': 10,
                     }       
        # Global default styles for all languages
        self.editorWindow.StyleSetSpec(wx.stc.STC_STYLE_DEFAULT,     "face:%(helv)s,size:%(size)d" % faces)
        self.editorWindow.StyleSetSpec(wx.stc.STC_STYLE_LINENUMBER,  "back:#C0C0C0,face:%(helv)s,size:%(size2)d" % faces)
        self.editorWindow.StyleSetSpec(wx.stc.STC_STYLE_CONTROLCHAR, "face:%(other)s" % faces)
        self.editorWindow.StyleSetSpec(wx.stc.STC_STYLE_BRACELIGHT,  "fore:#FFFFFF,back:#0000FF,bold")
        self.editorWindow.StyleSetSpec(wx.stc.STC_STYLE_BRACEBAD,    "fore:#000000,back:#FF0000,bold")
        
        # Python styles
        # White space
        self.editorWindow.StyleSetSpec(wx.stc.STC_P_DEFAULT, "fore:#808080,face:%(helv)s,size:%(size)d" % faces)
        # Comment
        self.editorWindow.StyleSetSpec(wx.stc.STC_P_COMMENTLINE, "fore:#007F00,face:%(other)s,size:%(size)d" % faces)
        # Number
        self.editorWindow.StyleSetSpec(wx.stc.STC_P_NUMBER, "fore:#007F7F,size:%(size)d" % faces)
        # String
        self.editorWindow.StyleSetSpec(wx.stc.STC_P_STRING, "fore:#7F007F,face:%(times)s,size:%(size)d" % faces)
        # Single quoted string
        self.editorWindow.StyleSetSpec(wx.stc.STC_P_CHARACTER, "fore:#7F007F,face:%(times)s,size:%(size)d" % faces)
        # Keyword
        self.editorWindow.StyleSetSpec(wx.stc.STC_P_WORD, "fore:#00007F,bold,size:%(size)d" % faces)
        # Triple quotes
        self.editorWindow.StyleSetSpec(wx.stc.STC_P_TRIPLE, "fore:#7F0000,size:%(size)d" % faces)
        # Triple double quotes
        self.editorWindow.StyleSetSpec(wx.stc.STC_P_TRIPLEDOUBLE, "fore:#7F0000,size:%(size)d" % faces)
        # Class name definition
        self.editorWindow.StyleSetSpec(wx.stc.STC_P_CLASSNAME, "fore:#0000FF,bold,underline,size:%(size)d" % faces)
        # Function or method name definition
        self.editorWindow.StyleSetSpec(wx.stc.STC_P_DEFNAME, "fore:#007F7F,bold,size:%(size)d" % faces)
        # Operators
        self.editorWindow.StyleSetSpec(wx.stc.STC_P_OPERATOR, "bold,size:%(size)d" % faces)
        # Identifiers
        self.editorWindow.StyleSetSpec(wx.stc.STC_P_IDENTIFIER, "fore:#808080,face:%(helv)s,size:%(size)d" % faces)
        # Comment-blocks
        self.editorWindow.StyleSetSpec(wx.stc.STC_P_COMMENTBLOCK, "fore:#007F00,size:%(size)d" % faces)
        # End of line where string is not closed
        self.editorWindow.StyleSetSpec(wx.stc.STC_P_STRINGEOL, "fore:#000000,face:%(mono)s,back:#E0C0E0,eol,size:%(size)d" % faces)
        

if __name__ == '__main__':
    app=wx.App()
    dlg = FileEditDialog(None, r'C:\Users\jqg93617\Documents\repos\beam-profiling\user_filter.py')

    dlg.ShowModal()