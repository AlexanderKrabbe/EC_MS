# -*- coding: utf-8 -*-
"""
Created on Fri Oct 14 16:50:10 2016
Most recently edited: 16J27

@author: scott




"""


from __future__ import division, print_function

import os, sys, pickle
import numpy as np
from matplotlib import pyplot as plt

if os.path.split(os.getcwd())[1] == 'EC_MS':
                                #then we're running from inside the package
    import Chem
    from EC import plot_CV_cycles, CV_difference, sync_metadata, select_cycles
    from Molecules import Molecule
    from Chips import Chip
    from Quantification import get_signal, get_current, get_potential
    print(os.getcwd())
    sys.exit()
else:                           #then we use relative import
    from . import Chem
    from .EC import plot_CV_cycles, CV_difference, sync_metadata, select_cycles
    from .Molecules import Molecule
    from .Chips import Chip
    from .Quantification import get_signal, get_current, get_potential
    from .Plotting import colorax, align_zero, plot_experiment

def ML_strip_cal(CV_and_MS, cycles=[1,2], t_int=200, cycle_str='cycle number',
             mol='CO2', mass='primary', n_el=None,
             Vspan=[0.5, 1.0], redox=1,
             ax='two', title='default', verbose=True,
             plot_instantaneous=False):
    '''
    Determines F_cal = Q_QMS / n_electrode by integrating a QMS signal over
    tspan, assuming the starting value is background; and
    integrating over vspan the difference between two CV cycles and converting
    that to a molar amount.
    Returns a partially populated calibration dictionary.
    The calibration factor is calibration['F_cal']
    '''
    if verbose:
        print('\n\ncalibration function \'ML_strip_cal\' at your service!\n')

    if ax == 'two':
        fig1 = plt.figure()
        ax1 = fig1.add_subplot(211)
        ax2 = fig1.add_subplot(212)
    elif ax is list:
        ax1 = ax[0]
        ax2 = ax[1]
    elif ax is None:
        ax1 = None
        ax2 = None
    else:
        ax1 = ax
        ax2 = None

    if type(mol) is str:
        mol = Molecule(mol, writenew=False)
    name = mol.name
    if n_el is None:
        n_el = mol.n_el
    if mass == 'primary':
        mass = mol.primary
    if np.size(t_int) == 1:
        #t_int = CV_and_MS['tspan_2'][0] + np.array([0, t_int]) #assumes I've cut stuff. Not necessarily true.
        #better solution below (17C22)
        pass
    if title == 'default':
        title = name + '_' + mass

#    print(type(CV_and_MS)) #was having a problem due to multiple outputs.
    cycles_data, ax1 = plot_CV_cycles(CV_and_MS, cycles, ax=ax1, title=title, cycle_str=cycle_str)
    ax1.xaxis.tick_top()
    ax1.xaxis.set_label_position('top')
#    print(type(cycles_data))
    Q_diff, diff = CV_difference(cycles_data, Vspan=Vspan, redox=redox, ax=ax1)
    #if ax1 is not None:
    #    ax1.set_title(title)

    n_mol = Q_diff / (Chem.Far * n_el)
    t = diff[0]
    J_diff = diff[2]
    A_el = CV_and_MS['A_el']

    if np.size(t_int) == 1: #17C22
        t_int = t[0] + np.array([0, t_int])
        #now it starts at the same time as EC data in the vrange starts

    #Q_diff seemed to be having a problem, but turned out to just be because
     #I forgot to remove_delay().
    # Now everything checks out, as can be seen here:
    '''
    Q_diff1 = A_el * np.trapz(J_diff, t) * 1e-3   #factor 1e-3 converts mA to A
    print('Q_diff = ' + str(Q_diff) +'\nQ_diff1 = ' + str(Q_diff1) +
          '\nratio = ' + str(Q_diff1/Q_diff))
    '''
    x = CV_and_MS[mass + '-x']
    y = CV_and_MS[mass + '-y']
    I_keep = [I for (I, x_I) in enumerate(x) if t_int[0] < x_I < t_int[1]]
    x = x[I_keep]
    y = y[I_keep]


    background = min(y)  #very simple background subtraction
    Q_QMS = np.trapz(y - background, x)
    F_cal = Q_QMS / n_mol

    y_el = J_diff * A_el/(Chem.Far * n_el) * F_cal * 1e-3
        #factor 1e-3 converts mA to A

    if ax2 is not None:
        ax2.plot(x,y*1e9, 'k-')
        #ax2.plot(x, [background*1e9]*len(x), 'k-')
        ax2.fill_between(x, background*1e9, y*1e9, where=y>background,
                         facecolor='g', interpolate=True)
        if plot_instantaneous:
            ax2.plot(t, y_el*1e9, 'r--')    #Without mass transport
        ax2.set_xlabel('time / s')
        ax2.set_ylabel('signal / nA')
#        ax2.set_yscale('log')


    print(('QMS measured {0:5.2e} C of charge at M44 for {1:5.2e} mol ' + name + '.\n' +
            'Calibration factor for CO2 at M44 is {2:5.2e} C / mol.'
            ).format(Q_QMS, n_mol, F_cal))

    calibration = {'type': 'ML_strip'}
    calibration['raw_data'] = CV_and_MS['title']
    calibration['mass'] = mass
    calibration['n_mol'] = n_mol
    calibration['Q_el'] = Q_diff
    calibration['Q_QMS'] = Q_QMS
    calibration['F_cal'] = F_cal
    calibration['title'] = title

    if verbose:
        print('\ncalibration function \'ML_strip_cal\' finished!\n\n')

    if ax2 is None:
        ax = ax1
    else:
        ax = [ax1, ax2]
    return calibration, ax



def steady_state_cal(CA_and_MS, t_int='half',
                     mol='CO2', mass='primary', n_el=None,
                     ax='new', title='default', verbose=True,
                     background='min'):
    if verbose:
        print('\n\ncalibration function \'steady_state_cal\' at your service!\n')
    if type(mol) is str:
        mol = Molecule(mol, writenew=False)
    name = mol.name
    if n_el is None:
        n_el = mol.n_el
    if mass == 'primary':
        mass = mol.primary
    if t_int == 'half':
        t_int = (CA_and_MS['tspan_2'][1] + np.array(CA_and_MS['tspan_2'])) / 2
    elif t_int == 'all':
        t_int =  np.array(CA_and_MS['tspan_2'])
    elif np.size(t_int) == 1:
        t_int = CA_and_MS['tspan_2'][1] + np.array([-t_int, 0])
        #by default integrate for time t_int up to end of interval
    if title == 'default':
        title = name + '_' + mass


    x = CA_and_MS[mass + '-x']
    y = CA_and_MS[mass + '-y']
    if background == 'min':
        background = min(y)
    elif background is None:
        background = 0
    I_keep = [I for (I, x_I) in enumerate(x) if t_int[0] < x_I < t_int[1]]
    x_r = x[I_keep]
    y_r = y[I_keep]
    Q_QMS = np.trapz(y_r - background, x_r)          #integrated signal in C

    V_str, J_str = sync_metadata(CA_and_MS)
    t = CA_and_MS['time/s']
    J = CA_and_MS[J_str]
    A_el = CA_and_MS['A_el']

    I_keep = [I for (I, t_I) in enumerate(t) if t_int[0] < t_I < t_int[1]]
    t_r = t[I_keep]
    J_r = J[I_keep]
    Q_el = A_el * np.trapz(J_r, t_r) * 1e-3 # total electrode charge passed in C
    n_mol = Q_el / (Chem.Far * n_el)

    F_cal = Q_QMS / n_mol

    y_el = J * A_el/(Chem.Far * n_el) * F_cal * 1e-3
    # expected QMS signal without mass transport etc

    print(('QMS measured {0:5.2e} C of charge at M44 for {1:5.2e} mol ' + name + '.\n' +
            'Calibration factor for CO2 at M44 is {2:5.2e} C / mol.'
            ).format(Q_QMS, n_mol, F_cal))

    if ax == 'new':
        fig1 = plt.figure()
        ax = fig1.add_subplot(111)
    if ax is not None:
        ax.plot(x, y, 'k-')
        ax.plot(t, y_el + background, 'r--')
        ax.set_title(title)

    calibration = {'type': 'steady_state'}
    calibration['raw_data'] = CA_and_MS['title']
    calibration['mass'] = mass
    calibration['n_mol'] = n_mol
    calibration['Q_el'] = Q_el
    calibration['Q_QMS'] = Q_QMS
    calibration['F_cal'] = F_cal

    if verbose:
        print('\ncalibration function \'steady_state_cal\' finished!\n\n')

    return calibration


def carrier_gas_cal(dataset=None, #if signal not given, reads average from dataset
                    signal=None,  #steady-state signal from in-flux of carrier gas
                    mol='He', #calibration Molecule object or name of calibration molecule
                    carrier = None,
                    viscosity = None,
                    mass='primary', #mass at which to calibrate
                    composition = 1, #mol fraction calibration molecule in carrier gas
                    chip='SI-3iv1-1-C5', #chip object or name of chip
                    tspan=None,
                    ):
    '''
    returns a calibration factor based the carrier gas concentration
    '''

    calibration = {'type': 'carrier gas'}

    if type(chip) is str:
        chip = Chip(chip)

    if type(mol) is str:
        mol = Molecule(mol)

    if carrier is None:
        carrier = mol
    elif type(carrier) is str:
        carrier = Molecule(carrier)

    if mass == 'primary':
        mass = mol.primary

    if type(composition) in (float, int):
        fraction = composition
    elif type(composition) is dict:
        fraction = composition[mol.name]

    n_dot = chip.capillary_flow(gas=carrier)

    n_dot_i = fraction * n_dot

    F_cal = signal/n_dot_i

    if signal is None:
        if tspan is None:
            tspan = dataset['txpan']
        x, y = get_signal(dataset, mass=mass, tspan=tspan)
        calibration['Q_QMS'] = np.trapz(y,x)
        signal = calibration['Q_QMS'] / (tspan[-1] - tspan[0])

        calibration['n_mol'] = n_dot_i * (tspan[-1] - tspan[0])

    calibration['mass'] = mass
    calibration['n_dot_i'] = n_dot_i
    calibration['signal'] = signal
    calibration['F_cal'] = F_cal

    return calibration


air_composition = {'N2':0.7808, 'O2':0.2095, 'Ar':0.0093, 'CO2':0.000412}

def chip_calibration(data, mol='O2', F_cal=None, primary=None, tspan=None,
                     tspan_bg=None, gas='air', composition=None, chip='SI-3iv1'):
    '''
    Returns obect of class EC_MS.Chip, given data for a given gas (typically air) for which
    one component (typically O2 at M32) has a trusted calibration. The chip object
    has a capillary length (l_cap) that is set so that the capillary flux matches
    the measured signal for the calibrated gas.
    '''

    if type(mol) is str:
        m = Molecule(mol)
    else:
        m = mol
        mol = mol.name
    if F_cal is not None:
        m.F_cal = F_cal
    if primary is not None:
        m.primary = primary

    if gas=='air' and composition is None:
        composition = air_composition[mol]

    x, y = m.get_flux(data, tspan=tspan, unit='mol/s')
    if tspan_bg is not None:
        x_bg, y_bg = m.get_flux(data, tspan=tspan_bg, unit='mol/s')
        y0 = np.mean(y_bg)
    else:
        y0 = 0
    n_dot = np.mean(y) - y0

    if type(chip) is str:
        chip = Chip(chip)
    n_dot_0 = chip.capillary_flow(gas=gas) / Chem.NA * composition

    l_eff = chip.l_cap * n_dot_0 / n_dot
    chip.l_cap = l_eff
    return chip


def point_calibration(data, mol, mass='primary', cal_type='internal',
                      tspan=None, n_el=None, tail=0, tspan_bg=None,
                      chip=None, composition=None, carrier=None,
                      ):
    '''
    Returns a molecule object calibrated based in one of the following ways.
        internally: cal_type='internal', need n_el
        externally: cal_type='external', need chip, carrier, composition
    The signal is taken as an average over the tspan, or at a linear
    extrapolated point if len(tspan)==1. Same for current for internal cal.
    For external calibration,
    '''

    m = Molecule(mol)
    if mass == 'primary':
        mass = m.primary
    if composition is None:
        if carrier==mol or carrier is None:
            composition = 1
        elif carrier == 'air':
            composition = air_composition[mol]

    #get average signal
    if tspan is None:
        tspan = data['tspan']
    if tspan_bg is not None:
        x_bg, y_bg = get_signal(data, mass, tspan=tspan_bg)
        y0 = np.mean(y_bg)
    else:
        y0 = 0
    if type(tspan) in [int, float]:
        x, y = get_signal(data, mass, [tspan-10, tspan+10])
        S = np.interp(tspan, x, y-y0)
    else:
        x, y = get_signal(data, mass, tspan=[tspan[0], tspan[1]+tail])
        S = np.trapz(y-y0, x) #/ (x[-1] - x[1])
       # S = np.mean(y) #more accurate for few, evenly spaced datapoints

    if cal_type == 'internal':
        if type(tspan) in [int, float]:
            t, i = get_current(data, tspan=[tspan-10, tspan+10], unit='A')
            I = np.interp(tspan, t, i)
        else:
            t, i = get_current(data, tspan=tspan, unit='A')
            I = np.trapz(i, t) #/ (t[-1] - t[1])
        n = I/(n_el*Chem.Far)

    elif cal_type == 'external':
        if chip is None:
            chip = 'SI-3iv1'
        if type(chip) is str:
            chip = Chip(chip)
        if carrier==None:
            carrier = mol
        n = chip.capillary_flow(gas=carrier) / Chem.NA * composition
        if type(tspan) not in [int, float]:
            n = n * (tspan[-1]- tspan[0])

    else:
        print('not sure what you mean, dude, when you say cal_type = \'' +
              cal_type + '\'')

    F_cal = S/n
    m.F_cal = F_cal

    return m



def calibration_curve(data, mol, mass='primary', n_el=-2,
                      cycles=None, cycle_str='selector',
                      mode='average', t_int=15, t_tail=30, t_pre=15,
                      background=None, t_bg=None, tspan_plot=None,
                      out='Molecule', ax='new', J_color='0.5', verbose=True
                      ):

    # ----- parse inputs -------- #
    m = Molecule(mol)
    if mass == 'primary':
        mass = m.primary

    if mode in ['average', 'averaging', 'mean']:
        mode = 'average'
    elif mode in ['integral', 'integrate', 'integrating']:
        mode = 'integral'

    use_bg_fun = False
    if t_bg is not None:
        x_bg, y_bg = get_signal(data, mass=mass, tspan=t_bg, unit='A')
        bg = np.mean(y_bg)
    elif callable(background):
        use_bg_fun = True
    elif background is not None:
        bg = background
    else:
        bg = 0

    # ---------- shit, lots of plotting options... ---------#
    ax1, ax2a, ax2b, ax2c = None, None, None, None
    fig1, fig2 = None, None
    if ax == 'new':
        ax1 = 'new'
        ax2 = 'new'
    else:
        try:
            iter(ax)
        except TypeError:
            ax2c = ax
        else:
            try:
                ax1, ax2 = ax
            except (TypeError, IndexError):
                print('WARNING: calibration_curve couldn\'t use the give axes')
    if ax1 == 'new':
        ax1 = plot_experiment(data, masses=[mass], tspan=tspan_plot,
                              emphasis=None, removebackground=False, unit='A')
        fig1 = ax1[0].get_figure()
    if ax2 == 'new':
        fig2, [ax2a, ax2c] = plt.subplots(ncols=2)
        ax2b = ax2a.twinx()
        fig2.set_figwidth(fig1.get_figheight()*3)
    else:
        try:
            iter(ax2)
        except TypeError:
            ax2c = ax2
        else:
            try:
                ax2a, ax2b, ax2c = ax
            except (TypeError, IndexError):
                print('WARNING: calibration_curve couldn\'t use the give ax2')


    # ----- cycle through and calculate integrals/averages -------- #
    Ys, ns, Vs = [], [], []
    for cycle in cycles:
        c = select_cycles(data, [cycle], cycle_str=cycle_str, verbose=verbose)
        t_end = c['time/s'][-1]
        t_start = c['time/s'][0]
        if mode == 'average':
            tspan = [t_end - t_int, t_end]
        elif mode == 'ingegral':
            c = select_cycles(data, [cycle-1, cycle, cycle+1], cycle_str=cycle_str,
                              t_zero=str(cycle), verbose=verbose)
            tspan = [t_start-t_pre, t_end+t_tail]

        t, I = get_current(c, tspan=tspan, verbose=verbose)
        t_v, v = get_potential(c, tspan=tspan, verbose=verbose)
        x, y = get_signal(c, mass=mass, tspan=tspan, verbose=verbose, unit='A')
        if use_bg_fun: # has to work on x.
            bg = background(x)

        V = np.mean(v)

        if mode == 'average':
            I_av = np.mean(I)
            n = I_av/(n_el*Chem.Far)
            Y = np.mean(y-bg)

        elif mode == 'integral':
            Q = np.trapz(I, t)
            n = Q/(n_el*Chem.Far)
            Y = np.trapz(y-bg, x)

        if ax1 is not None:
            color = m.get_color()
            try:
                iter(bg)
            except TypeError:
                y_bg = bg*np.ones(y.shape)
            else:
                y_bg = bg
            ax1[0].fill_between(x, y, y_bg, where=y>y_bg, color=color, alpha=0.5)
            J = I * 1e3 / data['A_el']
            J_bg = np.zeros(J.shape)
            ax1[2].fill_between(t, J, J_bg, color=J_color, alpha=0.5)

        ns += [n]
        Ys += [Y]
        Vs += [V]

    # ----- evaluate the calibration factor -------- #
    ns, Ys, Vs = np.array(ns), np.array(Ys), np.array(Vs)

    pfit = np.polyfit(ns, Ys, deg=1)
    F_cal = pfit[0]
    Y_pred = F_cal * ns + pfit[1]

    m.F_cal = F_cal

    # ----- plot the results -------- #
    color = m.get_color()
    ax2 = []
    if ax2a is not None: # plot the internal H2 calibration
        V_str, J_str = sync_metadata(data, verbose=False)
        if n_el < 0:
            ax2a.invert_xaxis()
        ax2a.plot(Vs, ns*1e9, '.-', color=J_color, markersize=10)
        ax2b.plot(Vs, Ys*1e9, 's', color=color)
        ax2a.set_xlabel(V_str)
        if mode == 'average':
            ax2a.set_ylabel('<I>/(' + str(n_el) + '$\mathcal{F}$) / [nmol s$^{-1}$]')
            ax2b.set_ylabel('<M2 signal> / nA')
        else:
            ax2a.set_ylabel('$\Delta$Q/(' + str(n_el) + '$\mathcal{F}$) / nmol')
            ax2b.set_ylabel('M2 signal / nC')
        colorax(ax2b, color)
        colorax(ax2a, J_color)
        align_zero(ax2a, ax2b)
        ax2 += [ax2a, ax2b]
    if ax2c is not None:
        ax2c.plot(ns*1e9, Ys*1e9, '.', color=color, markersize=10)
        ax2c.plot(ns*1e9, Y_pred*1e9, '--', color=color)
        if mode == 'average':
            ax2c.set_xlabel('<I>/(' + str(n_el) + '$\mathcal{F}$) / [nmol s$^{-1}$]')
            ax2c.set_ylabel('<M2 signal> / nA')
        else:
            ax2c.set_xlabel('$\Delta$Q/(' + str(n_el) + '$\mathcal{F}$) / nmol')
            ax2c.set_ylabel('M2 signal / nC')
        ax2 += [ax2c]

    # ------- parse 'out' and return -------- #
    possible_outs = {'ax':[ax1, ax2], 'fig':[fig1, fig2], 'Molecule':m,
                     'F_cal':F_cal, 'Vs':Vs, 'ns':ns, 'Ys':Ys}
    if type(out) is str:
        outs = possible_outs[out]
    else:
        outs = [possible_outs[o] for o in out]
    if verbose:
        print('\nfunction \'calibration_curve\' finished!\n\n')
    return outs


def save_calibration_results(mdict, f):
    calibration_results = {}
    for mol, m in mdict.items():
        result = {}
        for attr in ['primary', 'F_cal', 'cal_mat']:
            if hasattr(m, attr):
                result[attr] = getattr(m, attr)
        calibration_results[mol] = result
    if type(f) is str:
        with open(f, 'wb') as f:
            pickle.dump(calibration_results, f) # save it
    else: # then it must be a file
        pickle.dump(calibration_results, f) # save it

def load_calibration_results(f, verbose=True):
    if verbose:
        print('\n\nfunction \'load_calibration_results\' at your service!\n')
    if type(f) is str:
        with open(f, 'rb') as f: # load the calibrations!
            calibration_results = pickle.load(f)
    else:
        calibration_results = pickle.load(f)

    mdict = {} # turn the calibration results back into Molecule objects
    for mol, result in calibration_results.items():
        try:
            m = Molecule(mol, verbose=verbose)
        except FileNotFoundError:  # this happens if any molecule names were changed
            m = result
        else:
            for attr, value in result.items():
                setattr(m, attr, value)
        mdict[mol] = m
    if verbose:
        print('\nfunction \'load_calibration_results\' finished!\n\n')
    return mdict




