pro gain

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;
;    Parameters defining amplifier: size, stored energy, gain cross section......
;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;


f_stor       = 4.0                   ;stored (extractable) fluence in J/cm2
l_cryst      = 2.0                   ;gain medium thickness in cm
w_cryst      = 2.15                  ;width of gain medium in cm (actually of seed beam), assumes square shape
n_dope_int   = 4.38e20               ;doping atoms per cm2 (doping concentration times length)

c            = 3e8                   ;speed of light in m/s
h            = 6.626e-34             ;Planck's constant in J*s
lam_l        = 1030.                 ;laser wavelength in nm
f_lll        = 0.3 * 0.01            ;fractional thermal population lower laser level, temperature dependent
sigma_em     = 6.3e-20               ;emission cross section in cm^2 (temperature dependent)

e_phot_l     = h*c / (lam_l*1e-9)    ;laser photon energy in J
n_dope       = n_dope_int / l_cryst  ;doping concentration in 1/cm3

beta_mean    = (f_stor / (n_dope*e_phot_l * l_cryst)) - f_lll   ;average fractional uper laser level population at start

n_t          = 100                      ;number of time steps
n_slab       = 4                        ;number of gain media slabs
l_slab       = l_cryst / n_slab         ;thickness of slab

beta0        = fltarr(n_slab) + beta_mean  ; array to inital hold fractional upper laser level population, fltarr(n) function gnerates n-element array of floats, intialised to zero.
 
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;
;    Parameters defining amplification process: pulse energy, shape, duration, number of passes, losses....
;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;



t_ex = 10   * 1e-9    ;duration of extraction (or seed) pulse in s (first number is ns)
e_ex = 30   * 1e-3    ;initial energy of extraction pulse in J (first number is mJ)

dt_ex  = t_ex / n_t       ;lenght of time interval

n_pass = 7                ;number of passes

slab_loss = 0.5  * 0.01   ; optical loss between slabs,   1st number is % 
end_loss  = 5    * 0.01   ; optical loss after each pass, 1st number is %

t       = findgen(n_t) / (n_t - 1) * t_ex  ; time axis, findgen(n) generates array of floats of the form [0,1,2,3...n]

f_ex0   = e_ex / w_cryst^2 ; convert energy to fluence

f_ex    = fltarr(n_pass + 1, n_t) + (f_ex0 / n_t)    ;array to hold fluence of "pulselets" before and after each pass
                                                     ;and pre-poulate with input fluence, 
                                                     ;i.e. "fluence after 0th pass"
                                                     ;in this case square shaped pulse is assumed, but could be anything as long as total fluence is consistent with f_ex0 


beta      = fltarr(n_pass + 1, n_slab)  ;generate 2-dim array to hold beta after each passs
beta[0,*] = [beta0]                     ;pre-populate '0th' pass with initial beta

i_pass = 0
i_t = 0
i_z = 0

for i_pass = 1, n_pass do begin  ;run through passes

    beta [i_pass, *] =         beta[i_pass - 1, *]  ;pre-poulate beta,
    f_ex [i_pass, *] =         f_ex[i_pass - 1, *]  ;and f_ex for current pass

    for i_t = 0l, n_t - 1 do begin     ;run through time steps

        for i_z = 0l,  n_slab - 1 do begin  ;run through slabs
      
          f_ex_old          = f_ex[i_pass, i_t]   ;buffer variable to hold fluence of pulselet before it passes slab                     

          if i_z gt 0 then begin                    ; check if between slabs (i_z not eq 0)
              f_ex_old = f_ex_old * (1 - slab_loss)     ; if between slabs, apply losses between slabs
          endif
        
          f_ex[i_pass,i_t]  = f_ex_old * exp((beta[i_pass, i_z] - f_lll * (1 - beta[i_pass, i_z])) * sigma_em * n_dope * l_slab) ;amplified fluence of pulslet after passing through slab

          em_phot           = (f_ex[i_pass,i_t] - f_ex_old) / (e_phot_l*l_slab)                                                  ;number of emitted photons per unit volume (energy gain of pulselet)
          beta[i_pass,i_z]  = beta[i_pass, i_z] - em_phot   /  n_dope                                                            ;calculate new beta taking into account emitted photons
 
          ;print, "f_ex_old" , f_ex_old
          ;print, "f_ex" , f_ex[i_pass,i_t]
          ;print, "em_phot", em_phot
          ;print, "beta", beta[i_pass,i_z] 

        endfor

      f_ex[i_pass,i_t] = f_ex[i_pass, i_t] * (1-end_loss)  ;losses at end of pass         

    endfor

endfor

print,f_ex[7,*]

p_ex = f_ex / dt_ex * w_cryst^2  ; calculate output power in W

;openps
;
;plot, t*1e9, p_ex[n_pass,*] / 1e9, xtit = 'Time [ns]', ytit = 'Power [GW]', tit = 'Output Pulse Shape', xr = [-1,11],$
;      /nodata, xthick = 4, ythick = 4, xs = 1, /ylog, yr = [0.002,2], ys = 1
;      
;for i = 0, n_pass do begin
;  
;  oplot, t*1e9, p_ex[i,*] / 1e9, thick = 4, psym = 4, col = i*32
;  
;endfor
;
;Closeps

print, 'Output Energy [J]', total(f_ex[n_pass,*]) * w_cryst^2

end

