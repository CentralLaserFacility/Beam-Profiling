#############################################################
#  User defined filter that is applied to the AWG trace before appling.             
#                                                                                   
#  The function must be named awg_filter                                            
#                                                                                   
#  The function takes an array of any length and returns the filtered array, which  
#  must be of the same length                                                       
#                                                                                   
# ############################################################ 


from scipy.ndimage.filters import gaussian_filter1d
from scipy.signal import medfilt

def gaussian_filter(data):
    return gaussian_filter1d(data, sigma=1, order=0) 

def median_filter(data):
    return medfilt(data, 11)

def no_filter(data):
    return data


awg_filter =  gaussian_filter
