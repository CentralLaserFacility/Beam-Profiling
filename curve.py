import numpy as np
import wx
import matplotlib.pyplot as plt



class Curve:
    def __init__(self, curve_array=np.array([]), name = "unnamed"):
        """
        Creates a Curve object. The intialiser optionally takes the argument 
        curve_array, which is an array specifying the curve. Alternatively
        it initalises an array of zeros, and curves can be loaded from files
        using the load() method or by inputing arrays via the setter() method
        """

        self._num_points = 82
        self._trim_method = "off"
        self._curve = np.zeros(self._num_points)
        self._name = name
        
        if np.alen(curve_array) > 0:
            self._curve = curve_array
            self._num_points = np.alen(curve_array)
        
        self._processed = self._curve

    def name(self, name=None):
        if name:
            self._name = name
        else: 
            return self._name

    def load(self, num_points=None, trim_method=None, data=None, name=None):
        """
        load(num_points=None, trim_method=None)

        Load a curve file

        Parameters
        ----------
        num_points: int, optional
            The number of points required for the curve. If not set then the
            default number is used (usually 82)
        trim_method: string, optional
            The method used to manipulate the input into an array of num_points 
            in length. Options are 'resample' (default) and 'truncate'. If 'truncate'
            is chosen, arrays shorter that num_points are zero-padded. If 'off' the 
            full input array is output.
        data: ndarray or string, optional
            If an array is supplied, it will be read directly and num_points and trim_method are 
            ignored. If a string is passed, the file at that path will be loaded. If nothing is 
            passed, a file dialogue will be shown to choose the file.
        name: string, optional
            The name given to the curve. Defaults to either "manual" if data is supplied,
            or the filename of the loaded curve otherwise.

        Returns
        --------
        out: ndarray 
            A numpy array of length num_points to be accessed by the get_raw() method
        """

        if isinstance(data,np.ndarray):
            self._curve = data
            self._num_points = np.alen(data)
            self._processed = data
            
            if not name:
                self._name = "manual"
            else: 
                self._name = name
            return 0

        elif isinstance(data,str):
            pathname = data

        else:
            if not num_points:
                num_points = self._num_points

            if not trim_method:
                trim_method = self._trim_method

            #app = wx.App()
        
            frame = wx.Frame(None, -1, "Load a curve")
            frame.SetDimensions(0,0,200,50)

            with wx.FileDialog(frame, "Load Curve", 
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:

                if fileDialog.ShowModal() == wx.ID_CANCEL:
                    return -1   # Quit with no file loaded

                pathname = fileDialog.GetPath()

        try:
            self._curve = np.loadtxt(pathname)

            if trim_method == "resample":
                self._processed = self._resample(self._curve,num_points)
            elif trim_method == "truncate":
                self._processed = self._curve[:num_points]
                #pad if needed
                if np.size(self._processed) < num_points:
                    np.pad(self._processed,(0,num_points - np.size(self._processed)),'constant')
            elif trim_method == "off":
                self._processed = self._curve
            else:
                pass

            self._num_points = np.alen(self._processed)
            #self._processed = self._curve
            
            if not name:
                self._name = pathname.split('/')[-1]
            else: 
                self._name = name
            
            return 0

        except:
            print("Can't open the file")
            return -1
    
    def save(self, raw = False, pathname = None):
        """
        save(raw = False, pathname = None)
        
        Save the curve as a 1D array. 

        Parameters
        ----------

        raw: bool, optional
            If set to true, the raw curve data will be save, otherwise the processed
            curve is save.
        pathname: str, optional
            The full path to save the file under, including the filename. If left blank
            a file dialogue box will be launched to choose the location.

        Returns
        -------
        out: Text file containg a 1D array
        """

        if not pathname:
            #app = wx.App()
            
            frame = wx.Frame(None, -1, "Save the curve")
            frame.SetDimensions(0,0,200,50)

            with wx.FileDialog(frame, "Save Curve", 
                            style=wx.FD_SAVE) as fileDialog:

                if fileDialog.ShowModal() == wx.ID_CANCEL:
                    return    # Quit with no save

                pathname = fileDialog.GetPath()

        try:
            if raw:
                np.savetxt(pathname,self._curve)
            else:
                np.savetxt(pathname,self._processed)

        except:
            print("Couldn't save the file")

    def process(self, *args, **kwargs):
        """
        process('clip','norm','bkg' = curve_instance, 'crop' = (start_point, length), 'resample' = new_size)

        Process the curve to prepare for the feedback loop. Each this is run it starts from the 
        raw curve data, so all desired processing parms must be specified each time.

        Parameters
        ----------

        args:
            "clip", optional:
                Clip the negative values of the curve, replacing with zeros
            "norm", optional
                Normalise the values to 1
        
        kwargs:
            "bkg", optional: Instance of Curve object
                The Curve containing the background trace to be used
            "crop", optional: tuple of ints
                Slice the trace, starting at start_point for length pixels 
            "resample", optional: int
                Resample the curve to new_size

        Returns
        -------
        Results in a processed curve to be accessed by the get_processed() method

        """

        # Reset the curve first
        self._processed = self._curve

        supported_args = ["bkg", "crop", "clip", "norm","resample"]

        # Since the order in which this is done is vital, and we can't rely
        # on preserving in the order of **kwargs before python 3.6, go through
        # and set flags first then deal with them in the right order. 

        do_bkg = do_crop = do_resample = do_clip = do_norm = False

        for arg in args:
            if arg == "clip":
                do_clip = True
            if arg == "norm":
                do_norm = True
            if arg not in supported_args:
                print("Unrecognised argument: %s" % arg)

        for key, value in kwargs.iteritems():
            if key == "bkg":
                do_bkg = True
                val_bkg = value
            if key == "crop":
                do_crop = True
                val_crop = value
            if key == "resample":
                do_resample = True
                val_resample = value
            if key not in supported_args:
                print("Unrecognised keyword: %s" % key)

       
        if do_bkg:
            # value of "bkg" should be an instance of Curve
            #print "Sizes %d %d" % (np.size(self._processed), np.size(val_bkg.get_raw()) )
            self._processed = self._processed - val_bkg.get_raw()
            pass
        if do_crop:
            self._processed = self._processed[val_crop[0]:val_crop[0+1]]
        if do_resample:
            self._processed = self._resample(self._processed, val_resample)           
        if do_clip:
            self._processed = self._clip_neg(self._processed)
        if do_norm:
            self._processed = self._normalise(self._processed)

    # Needs rewrite to average over blocks of 5 points at a time
    def _resample(self, data, npoints):
        im = np.arange(0,len(data))
        factor = len(data)/float(npoints)
        ip = np.arange(0, len(data), factor)
        p = np.interp(ip, im, data)
        return p

    def _clip_neg(self, data):
        return np.clip(data,0,np.amax(data))

    def _normalise(self,data):
        if np.amax(np.abs(data)) != 0:
            return data/np.amax(np.abs(data))
        else:
            return data

    def get_raw(self):
        return self._curve

    def get_processed(self):
        return self._processed

    def plot_raw(self, *args, **kwargs):
        plt.plot(self._curve, *args, **kwargs)
        plt.show(block=True)

    def plot_processed(self, *args, **kwargs):
        plt.plot(self._processed, *args, **kwargs)
        plt.show(block=True)

    def plot_all(self):
        plt.plot(self._curve, 'g--')
        plt.plot(self._processed, 'b')
        plt.show(block=True)

    def plot_clear(self):
        plt.clf()
        plt.draw()
    
    def print_size(self):
        print "Curve %s size: %d" % (self.name(), np.alen(self.get_raw()))

        
class BkgCurve(Curve):
    '''The same a the Curve class, but modify the process methods as we don't want 
        to be able to subtract background from a background curve'''

    def __init__(self, curve_array=np.array([]), name = "unnamed"):
        Curve.__init__(self, curve_array, name)

    def process(self, *args, **kwargs):
        """
        process('clip','norm','bkg' = curve_instance, 'crop' = (start_point, length), 'resample' = new_size)

        Process the curve to prepare for the feedback loop. Each this is run it starts from the 
        raw curve data, so all desired processing parms must be specified each time.

        Parameters
        ----------

        args:
            "clip", optional:
                Clip the negative values of the curve, replacing with zeros
            "norm", optional
                Normalise the values to 1
        
        kwargs:
            "bkg", optional: Instance of Curve object
                The Curve containing the background trace to be used
            "crop", optional: tuple of ints
                Slice the trace, starting at start_point for length pixels 
            "resample", optional: int
                Resample the curve to new_size

        Returns
        -------
        Results in a processed curve to be accessed by the get_processed() method

        """

        # Reset the curve first
        self._processed = self._curve

        supported_args = ["bkg", "crop", "clip", "norm","resample"]

        # Since the order in which this is done is vital, and we can't rely
        # on preserving in the order of **kwargs before python 3.6, go through
        # and set flags first then deal with them in the right order. 

        do_bkg = do_crop = do_resample = do_clip = do_norm = False

        for arg in args:
            if arg == "clip":
                do_clip = True
            if arg == "norm":
                do_norm = True
            if arg not in supported_args:
                print("Unrecognised argument: %s" % arg)

        for key, value in kwargs.iteritems():
            if key == "bkg":
                print "Ignoring keyword: bkg. Background curves don't support background subtraction"
            if key == "crop":
                do_crop = True
                val_crop = value
            if key == "resample":
                do_resample = True
                val_resample = value
            if key not in supported_args:
                print("Unrecognised keyword: %s" % key)

        if do_crop:
            self._processed = self._processed[val_crop[0]:val_crop[0+1]]
        if do_resample:
            self._processed = self._resample(self._processed, val_resample)           
        if do_clip:
            self._processed = self._clip_neg(self._processed)
        if do_norm:
            self._processed = self._normalise(self._processed)


class TargetCurve(Curve):
    '''The same a the Curve class, but modify the process methods as we don't want 
        to be able to subtract background from a target curve'''

    def __init__(self, curve_array=np.array([]), name = "unnamed"):
        Curve.__init__(self, curve_array, name)

    def process(self, *args, **kwargs):
        """
        process('clip','norm','bkg' = curve_instance, 'crop' = (start_point, length), 'resample' = new_size)

        Process the curve to prepare for the feedback loop. Each this is run it starts from the 
        raw curve data, so all desired processing parms must be specified each time.

        Parameters
        ----------

        args:
            "clip", optional:
                Clip the negative values of the curve, replacing with zeros
            "norm", optional
                Normalise the values to 1
        
        kwargs:
            "bkg", optional: Instance of Curve object
                The Curve containing the background trace to be used
            "crop", optional: tuple of ints
                Slice the trace, starting at start_point for length pixels 
            "resample", optional: int
                Resample the curve to new_size

        Returns
        -------
        Results in a processed curve to be accessed by the get_processed() method

        """

        # Reset the curve first
        self._processed = self._curve

        supported_args = ["bkg", "crop", "clip", "norm","resample"]

        # Since the order in which this is done is vital, and we can't rely
        # on preserving in the order of **kwargs before python 3.6, go through
        # and set flags first then deal with them in the right order. 

        do_bkg = do_crop = do_resample = do_clip = do_norm = False

        for arg in args:
            if arg == "clip":
                do_clip = True
            if arg == "norm":
                do_norm = True
            if arg not in supported_args:
                print("Unrecognised argument: %s" % arg)

        for key, value in kwargs.iteritems():
            if key == "bkg":
                print "Ignoring keyword: bkg. Target curves don't support background subtraction"
            if key == "crop":
                do_crop = True
                val_crop = value
            if key == "resample":
                do_resample = True
                val_resample = value
            if key not in supported_args:
                print("Unrecognised keyword: %s" % key)

        if do_crop:
            self._processed = self._processed[val_crop[0]:val_crop[0+1]]
        if do_resample:
            self._processed = self._resample(self._processed, val_resample)           
        if do_clip:
            self._processed = self._clip_neg(self._processed)
        if do_norm:
            self._processed = self._normalise(self._processed)   
    
