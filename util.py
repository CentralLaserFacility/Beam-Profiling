from datetime import datetime    

# Provides a date and time string for messages printed to the console
def get_message_time():
    return datetime.now().strftime("%b_%d_%H:%M.%S")+": "

# Holds utility constants
class CODES():
    Proceed = 1 
    Recalc = 2
    Abort = 3
    Pause = 4 
    Error = 5 
    NoError = 6

# This is used in the constructor of loop frame to redirect output from
# stdout to log panel
class RedirectText(object):
    def __init__(self,aWxTextCtrl):
        self.out=aWxTextCtrl
 
    def write(self,string):
        self.out.WriteText(string)
