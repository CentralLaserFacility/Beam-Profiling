import numpy as np
import math
import sys
import util

class Model:

    def __init__(self, input_energy=30*1e-3, input_pulse_length=10*1e-9, n_time_step=100, n_slab=4, n_pass=7):

        f_stor = 4.0                            # stored fluence in J/cm2
        l_cryst = 2.0                           # gain medium thickness in cm
        self.w_cryst = 2.15                     # width of gain medium in cm (seed beam), assumes square shape
        n_dope_int = 4.38e20                    # doping atoms per cm2 (doping concentration times length)

        c = 3e8                                 # speed of light in m/s
        h = 6.626e-34                           # Planck's constant in J*s
        lam_1 = 1030.0                          # laser wavelength in nm
        self.f_lll = 0.3 * 0.01                 # fractional thermal population lower laser level
        self.sigma_em = 6.3e-20                 # emission cross section in cm2 (temperature dependent)

        self.e_phot_l = h*c / (lam_1*1e-9)      # laser photon energy in J
        self.n_dope = n_dope_int / l_cryst      # doping concentration in 1/cm3

        self.n_t = n_time_step                  # number of time steps
        self.n_slab = n_slab                    # number of gain media slabs
        self.l_slab = l_cryst / self.n_slab     # thickness of slab

        t_ex = input_pulse_length               # duration of extraction (or seed) pulse in s (1st number is ns)
        self.e_ex = input_energy                     # initial energy of extraction pulse in J (1st number in mJ)

        self.dt_ex = t_ex / self.n_t            # length of time interval

        self.n_pass = n_pass                    # number of passes

        self.slab_loss = 0.5*0.01               # optical loss between slabs (1st number is %)
        self.end_loss = 5*0.01                  # optical loss after each pass (1st number is %)

        # time axis
        t = np.arange(0,self.n_t,1.0)
        t = [ x / (self.n_t-1) * t_ex for x in t]
        self.t = np.asarray(t)

        # average fractional upper level population at start
        beta_mean = (f_stor / (self.n_dope*self.e_phot_l * l_cryst)) - self.f_lll 

        # array to hold fractional upper level laser level population
        beta0 = np.full(self.n_slab,beta_mean)
        self.beta = np.zeros((self.n_pass + 1 , self.n_slab))
        self.beta[0,:] = beta0

        #input energy
        self.f_ex0 = self.e_ex / self.w_cryst**2 # convert energy to fluence
        self.f_ex = np.full((self.n_pass+1,self.n_t),self.f_ex0/self.n_t)
 

    def set_input_shape(self, input_shape):
        inp = util.normalise(input_shape)
        self.f_ex = np.empty((self.n_pass+1,self.n_t))
        for i_pass in range(0, self.n_pass+1): self.f_ex[i_pass] = inp * (self.e_ex / self.w_cryst**2) / self.n_t

    def simulate(self):

        for i_pass in range(1, self.n_pass+1): #run through passes

            # prepopulate current 
            self.beta[i_pass,:] = self.beta[i_pass-1,:]
            self.f_ex[i_pass,:] = self.f_ex[i_pass-1,:]

            for i_t  in range(0, self.n_t): #run through time steps

                for i_z in range(0, self.n_slab): #run through slabs            

                    # fluence of pulselet before it passes the slab
                    f_ex_old = self.f_ex[i_pass,i_t]

                    # apply energy loss between slabs
                    if i_z > 0: f_ex_old = f_ex_old * (1.0 - self.slab_loss)

                    # amplified fluence of pulselet after passing through slab
                    self.f_ex[i_pass,i_t] = f_ex_old * math.exp((self.beta[i_pass,i_z] - self.f_lll * (1.0-self.beta[i_pass,i_z])) * self.sigma_em * self.n_dope * self.l_slab)

                    # number of emitted phtons per unit volume (energy gain of pulselet)
                    em_phot = (self.f_ex[i_pass,i_t] - f_ex_old) / (self.e_phot_l * self.l_slab)
                   
                    # calculate new beta talking into account emitted photons
                    self.beta[i_pass,i_z] = self.beta[i_pass,i_z] - em_phot / self.n_dope

                # caculate losses at end of pass
                self.f_ex[i_pass,i_t] = self.f_ex[i_pass,i_t] * (1.0-self.end_loss)

    def plot(self):
        import matplotlib.pyplot as plt
        for i in range(self.n_pass+1): plt.plot(util.normalise(self.f_ex[i]))
        plt.title("Pulse Shape Modelling")
        plt.show()

    def get_output_energy(self):
        o_ex = np.sum(self.f_ex[self.n_pass,:])
        o_ex *= self.w_cryst**2
        return o_ex

    def get_output_shape(self):
        return util.normalise(self.f_ex[self.n_pass])


if __name__ == "__main__":
    model = Model()
    model.simulate()
    model.plot()
    
    
