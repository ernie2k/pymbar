# Example illustrating the application of MBAR to compute a 1D PMF from an umbrella sampling simulation.
#
# The data represents an umbrella sampling simulation for the chi torsion of a valine sidechain in lysozyme L99A with benzene bound in the cavity.
# 
# REFERENCE
# 
# D. L. Mobley, A. P. Graves, J. D. Chodera, A. C. McReynolds, B. K. Shoichet and K. A. Dill, "Predicting absolute ligand binding free energies to a simple model site," Journal of Molecular Biology 371(4):1118-1134 (2007).
# http://dx.doi.org/10.1016/j.jmb.2007.06.002

from __future__ import print_function
import matplotlib.pyplot as plt
from scipy.interpolate import BSpline
nplot = 1000
# set minimizer options to display. Apprently does not exist for BFGS. Probably don't need to set eps.
optimize_options = {'disp':True, 'tol':10**(-3)}
#methods = ['histogram','kde','sumkl-3','sumkl-3','simple-3','weighted-3']
methods = ['kde','simple-3']
#optimization_algorithm = 'L-BFGS-B'
optimization_algorithm = 'Custom-NR'
#optimization_algorithm = 'Newton-CG'
colors = dict()
colors['histogram'] = 'k:'
colors['kde'] = 'k-'
colors['kl-1'] = 'g-'
colors['kl-3'] = 'm-'
colors['kl-5'] = 'c-'
colors['sumkl-1'] = 'g--'
colors['sumkl-3'] = 'm--'
colors['sumkl-5'] = 'c--'
colors['simple-1'] = 'g-.'
colors['simple-3'] = 'm-.'
colors['simple-5'] = 'c-.'
colors['weighted-1'] = 'g:'
colors['weighted-3'] = 'm:'
colors['weighted-5'] = 'c:'

# example illustrating the application of MBAR to compute a 1D PMF from an umbrella sampling simulation.
#
# The data represents an umbrella sampling simulation for the chi torsion of a valine sidechain in lysozyme L99A with benzene bound in the cavity.
# 
# REFERENCE
# 
# D. L. Mobley, A. P. Graves, J. D. Chodera, A. C. McReynolds, B. K. Shoichet and K. A. Dill, "Predicting absolute ligand binding free energies to a simple model site," Journal of Molecular Biology 371(4):1118-1134 (2007).
# http://dx.doi.org/10.1016/j.jmb.2007.06.002
import pdb
from timeit import default_timer as timer
import numpy as np # numerical array library
import pymbar # multistate Bennett acceptance ratio
from pymbar import timeseries # timeseries analysis
from pymbar import PMF
# Constants.
kB = 1.381e-23 * 6.022e23 / 1000.0 # Boltzmann constant in kJ/mol/K


temperature = 300 # assume a single temperature -- can be overridden with data from center.dat 
# Parameters
K = 26 # number of umbrellas
N_max = 501 # maximum number of snapshots/simulation
T_k = np.ones(K,float)*temperature # inital temperatures are all equal 
beta = 1.0 / (kB * temperature) # inverse temperature of simulations (in 1/(kJ/mol))
chi_min = -180.0 # min for PMF
chi_max = +180.0 # max for PMF
nbins = 40 # number of bins for 1D PMF. Note, does not have to correspond to the number of umbrellas at all.
nsplines = 15
nbootstraps = 0
# Allocate storage for simulation data
N_k = np.zeros([K], np.int32) # N_k[k] is the number of snapshots from umbrella simulation k
K_k = np.zeros([K], np.float64) # K_k[k] is the spring constant (in kJ/mol/deg**2) for umbrella simulation k
chi0_k = np.zeros([K], np.float64) # chi0_k[k] is the spring center location (in deg) for umbrella simulation k
chi_kn = np.zeros([K,N_max], np.float64) # chi_kn[k,n] is the torsion angle (in deg) for snapshot n from umbrella simulation k
u_kn = np.zeros([K,N_max], np.float64) # u_kn[k,n] is the reduced potential energy without umbrella restraints of snapshot n of umbrella simulation k
g_k = np.zeros([K],np.float32);

# Read in umbrella spring constants and centers.
infile = open('data/centers.dat', 'r')
lines = infile.readlines()
infile.close()
for k in range(K):
    # Parse line k.
    line = lines[k]
    tokens = line.split()
    chi0_k[k] = float(tokens[0]) # spring center locatiomn (in deg)
    K_k[k] = float(tokens[1]) * (np.pi/180)**2 # spring constant (read in kJ/mol/rad**2, converted to kJ/mol/deg**2)    
    if len(tokens) > 2:
        T_k[k] = float(tokens[2])  # temperature the kth simulation was run at.

beta_k = 1.0/(kB*T_k)   # beta factor for the different temperatures
DifferentTemperatures = True
if (min(T_k) == max(T_k)):
    DifferentTemperatures = False            # if all the temperatures are the same, then we don't have to read in energies.
# Read the simulation data
for k in range(K):
    # Read torsion angle data.
    filename = 'data/prod%d_dihed.xvg' % k
    print("Reading {:s}...".format(filename))
    infile = open(filename, 'r')
    lines = infile.readlines()
    infile.close()
    # Parse data.
    n = 0
    for line in lines:
        if line[0] != '#' and line[0] != '@':
            tokens = line.split()
            chi = float(tokens[1]) # torsion angle
            # wrap chi_kn to be within [-180,+180)
            while(chi < -180.0):
                chi += 360.0
            while(chi >= +180.0):
                chi -= 360.0
            chi_kn[k,n] = chi
            
            n += 1
    N_k[k] = n

    if (DifferentTemperatures):  # if different temperatures are specified the metadata file, 
                                 # then we need the energies to compute the PMF
        # Read energies
        filename = 'data/prod%d_energies.xvg' % k
        print("Reading {:s}...".format(filename))
        infile = open(filename, 'r')
        lines = infile.readlines()
        infile.close()
        # Parse data.
        n = 0
        for line in lines:
            if line[0] != '#' and line[0] != '@':
                tokens = line.split()            
                u_kn[k,n] = beta_k[k] * (float(tokens[2]) - float(tokens[1])) # reduced potential energy without umbrella restraint
                n += 1

    # Compute correlation times for potential energy and chi
    # timeseries.  If the temperatures differ, use energies to determine samples; otherwise, use the cosine of chi
            
    if (DifferentTemperatures):        
        g_k[k] = timeseries.statisticalInefficiency(u_kn[k,:], u_kn[k,0:N_k[k]])
        print("Correlation time for set {:5d} is {:10.3f}".format(k,g_k[k]))
        indices = timeseries.subsampleCorrelatedData(u_kn[k,0:N_k[k]])
    else:
        chi_radians = chi_kn[k,0:N_k[k]]/(180.0/np.pi)
        g_cos = timeseries.statisticalInefficiency(np.cos(chi_radians))
        g_sin = timeseries.statisticalInefficiency(np.sin(chi_radians))
        print("g_cos = {:.1f} | g_sin = {:.1f}".format(g_cos, g_sin))
        g_k[k] = max(g_cos, g_sin)
        print("Correlation time for set {:5d} is {:10.3f}".format(k,g_k[k]))
        indices = timeseries.subsampleCorrelatedData(chi_radians, g=g_k[k]) 
    # Subsample data.
    N_k[k] = len(indices)
    u_kn[k,0:N_k[k]] = u_kn[k,indices]
    chi_kn[k,0:N_k[k]] = chi_kn[k,indices]

N_max = np.max(N_k) # shorten the array size
u_kln = np.zeros([K,K,N_max], np.float64) # u_kln[k,l,n] is the reduced potential energy of snapshot n from umbrella simulation k evaluated at umbrella l

# Set zero of u_kn -- this is arbitrary.
u_kn -= u_kn.min()

# Construct torsion bins
# compute bin centers

bin_center_i = np.zeros([nbins], np.float64)
bin_edges = np.linspace(chi_min,chi_max,nbins+1)
for i in range(nbins):
    bin_center_i[i] = 0.5*(bin_edges[i] + bin_edges[i+1])

N = np.sum(N_k)
x_n = np.zeros(N,np.int32)
chi_n = pymbar.utils.kn_to_n(chi_kn, N_k = N_k)

ntot = 0
for k in range(K):
    for n in range(N_k[k]):
        # Compute bin assignment.
        x_n[ntot] = chi_kn[k,n]
        ntot +=1

# Evaluate reduced energies in all umbrellas
print("Evaluating reduced potential energies...")
for k in range(K):
    for n in range(N_k[k]):
        # Compute minimum-image torsion deviation from umbrella center l
        dchi = chi_kn[k,n] - chi0_k
        for l in range(K):
            if (abs(dchi[l]) > 180.0):
                dchi[l] = 360.0 - abs(dchi[l])

        # Compute energy of snapshot n from simulation k in umbrella potential l
        u_kln[k,:,n] = u_kn[k,n] + beta_k[k] * (K_k/2.0) * dchi**2

# Initialize histogram PMF for comparison:
#initialize PMF with the data collected
pmf = pymbar.PMF(u_kln, N_k, verbose = True)

# define the bias potentials needed for some method
def bias_potential(x,k):
    dchi = x - chi0_k[k]
    # vectorize the conditional
    i = np.fabs(dchi) > 180.0
    dchi = i*(360.0 - np.fabs(dchi)) + (1-i)*dchi
    return beta_k[k]* (K_k[k] /2.0) * dchi**2

times = dict() # keep track of times each method takes

xplot = np.linspace(chi_min,chi_max,nplot)
f_i_kde = None # We check later if these have been defined or not
xstart = np.linspace(chi_min,chi_max,nsplines*2)

for method in methods:
    start = timer()

    if method == 'histogram':

        histogram_parameters = dict()
        histogram_parameters['bin_edges'] = [bin_edges]
        pmf.generatePMF(u_kn, chi_n, pmf_type = 'histogram', histogram_parameters=histogram_parameters, nbootstraps=nbootstraps)

    if method == 'kde':

        kde_parameters = dict()
        kde_parameters['bandwidth'] = 0.5*((chi_max-chi_min)/nbins)
        pmf.generatePMF(u_kn, chi_n, pmf_type = 'kde', kde_parameters=kde_parameters, nbootstraps=nbootstraps)

        # save this for initializing other types
        results = pmf.getPMF(xstart, uncertainties = 'from-lowest')
        f_i_kde = results['f_i']  # kde results

    if method[:2] == 'kl' or method[:5] == 'sumkl' or  method[:8] == 'weighted' or method[:6] == 'simple':
        spline_parameters = dict()
        if method[:2] == 'kl':
            spline_parameters['spline_weights'] = 'kldivergence'
        if method[:5] == 'sumkl':
            spline_parameters['spline_weights'] = 'sumkldivergence'
        if method[:8] == 'weighted':
            spline_parameters['spline_weights'] = 'weightedsum'
        if method[:6] == 'simple':
            spline_parameters['spline_weights'] = 'simplesum'

        spline_parameters['nspline'] = nsplines
        spline_parameters['spline_initialize'] = 'explicit'

        # need to initialize: use KDE results for now (assumes KDE exists)
        spline_parameters['xinit'] = xstart
        if f_i_kde is not None:
            spline_parameters['yinit'] = f_i_kde
        else:
            spline_parameters['yinit'] = np.zeros(len(xstart))

        spline_parameters['xrange'] = [chi_min,chi_max]

        spline_parameters['fkbias'] = [(lambda x, klocal=k: bias_potential(x,klocal)) for k in range(K)]  # introduce klocal to force K to use local definition of K, otherwise would use global value of k.

        spline_parameters['kdegree'] = int(method[-1])
        spline_parameters['optimization_algorithm'] = optimization_algorithm
        spline_parameters['optimize_options'] = optimize_options
        pmf.generatePMF(u_kn, chi_n, pmf_type = 'spline', spline_parameters=spline_parameters, nbootstraps=nbootstraps)

    end = timer()
    times[method] = end-start

    yout = dict()
    yerr = dict()
    print("PMF (in units of kT) for {:s}".format(method))
    print("{:8s} {:8s} {:8s}".format('bin', 'f', 'df'))
    results = pmf.getPMF(bin_center_i, uncertainties = 'from-lowest')
    for i in range(nbins):
        if results['df_i'] is not None:
            print("{:8.1f} {:8.1f} {:8.1f}".format(bin_center_i[i], results['f_i'][i], results['df_i'][i]))
        else:
            print("{:8.1f} {:8.1f}".format(bin_center_i[i], results['f_i'][i]))

    results = pmf.getPMF(xplot, uncertainties = 'from-lowest')
    yout[method] = results['f_i']
    yerr[method] = results['df_i']
    if len(xplot) <= 50:
        errorevery = 1
    else:
        errorevery = np.floor(len(xplot)/50)

    plt.errorbar(xplot,yout[method],yerr=yerr[method],errorevery=errorevery,label=method,fmt=colors[method])

plt.xlim([chi_min,chi_max])
plt.legend()
plt.savefig('compare_pmf_{:d}.pdf'.format(nsplines))

for method in methods:
    print("time for method {:s} is {:2f} s".format(method,times[method]))

#now, plot these
mc_parameters = {"niterations":10000, "fraction_change":0.02, "sample_every": 50, 
                 "prior": lambda x: 1,"print_every":100}

csamples, logposteriors, bspline = pmf.SampleDistribution(chi_n, pmf_type = 'spline', 
                                                          spline_parameters = spline_parameters, 
                                                          mc_parameters = mc_parameters)
plt.clf()
plt.hist(logposteriors)
plt.savefig('posterior.pdf')

# determine confidence intervals
nsamples = len(logposteriors)
samplevals = np.zeros([nplot,nsamples])
for n in range(nsamples):
    pcurve = BSpline(bspline.t,csamples[:,n],bspline.k)
    samplevals[:,n] = pcurve(xplot)

# now determine 
ylows = np.zeros(len(xplot))
yhighs = np.zeros(len(xplot))
ymedians = np.zeros(len(xplot))
for n in range(len(xplot)):
    ylows[n] = np.percentile(samplevals[n,:],17)
    yhighs[n] = np.percentile(samplevals[n,:],83)
    ymedians[n] = np.percentile(samplevals[n,:],50)
plt.clf()
plt.plot(xplot,yout[method],colors[method],label=method)
plt.fill_between(xplot,ylows-ymedians+yout[method],yhighs-ymedians+yout[method],color=colors[method][0],alpha=0.3)
plt.legend()
plt.savefig('bayesian.pdf')