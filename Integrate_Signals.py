# -*- coding: utf-8 -*-
"""
Created on Tue Aug  2 22:50:34 2016
Most recently edited: 16I23

@author: Scott

This module has functions for integrating and averaging signals over specified
time frames or cycles, mostly for pulsed electrolysis experiments.
"""
# make python2-compatible:
from __future__ import print_function
from __future__ import division

import numpy as np
from matplotlib import pyplot as plt
import os

if os.path.split(os.getcwd())[1] == 'EC_MS':
                                #then we're running from inside the package
    from Plotting import plot_experiment
    from EC import select_cycles
    from Quantification import get_flux, get_potential, get_current
else:                           #then we use relative import
    from .Plotting import plot_experiment
    from .EC import select_cycles
    from .Quantification import get_flux, get_potential, get_current



def get_datapoints(dataset, cycles, mols=['H2','C2H4','CH4'],
                   tspan=[0, 100], t_steady=[50, 60], Vcycle=0,
                   transient='CH4', colors=None, cycle_str=None,
                   plotcycles=False, plottransient=False, data_type='CA',
                   verbose=True):
    '''
    Ways to control this function:
    (1) put in a dictionary for mols with plotting colors and sub-dictionaries
    for products that should be split into transient ('dyn') and steady-state ('ss')
    for example, mols={'C2H4':'g', 'CH4':{'ss':'r','dyn':[0.8, 0, 0]}
    All transient integrations will use same t_steady
    (2)
    '''
    if verbose:
        print('\n\nfunction \'get_datapoints\' at your service!\n')
    #interpret inputs.
    if type(mols) is dict:
        colors = mols.copy()
    if colors is None:
        colors = mols
        if type(mols) is dict:
            mols = list(mols.keys())
        if type(transient) is str:
            transient = [transient]
    else:
        mols = list(colors.keys())
        transient = [mol for (mol, value) in colors.items() if type(value) is dict]
    if type(t_steady) is dict:
        transient = list(t_steady.keys())
    else:
        ts = t_steady
        t_steady = {}
    if type(colors) is dict:
        for mol in transient:
            if type(colors[mol]) is dict:
                colors[mol] = colors[mol]['ss']
                #just for plotting cycles with appropriate colors
    if Vcycle in ['previous', 'last', 'rest']:
        Vcycle = -1
    elif Vcycle in ['present', 'current', 'same', 'work']:
        Vcycle = 0
    elif Vcycle in ['next']:
        Vcycle = 1
    V_str = dataset['V_str']

    #prepare space for results:
    V = []
    integrals={}
    for mol in mols:
        if mol in transient:
            integrals[mol] = {'ss':[], 'dyn':[]}
            if mol not in t_steady.keys():
                t_steady[mol] = ts
        else:
            integrals[mol] = []

    #get results:
    for cycle in cycles:
        off_data = select_cycles(dataset, cycles=cycle+Vcycle, t_zero='start',
                                 data_type=data_type, cycle_str=cycle_str, verbose=verbose)
        #off_data is data from the cycle that the independent variable is obtained form
        on_data = select_cycles(dataset, cycles=[cycle, cycle+1], t_zero='start',
                                data_type=data_type, cycle_str=cycle_str, verbose=verbose)
        #on_data is data from the cycle, and following cycle for the tail, that the dependent variable is obtained from

        t_off = off_data['time/s']
        V_off = off_data[V_str]
        V += [np.trapz(V_off, t_off) / (t_off[-1] - t_off[0])]

        if plotcycles:
            title = str(cycle) + ', U = ' + str(V[-1])
            plot_experiment(on_data, mols=colors, title=title,
                            verbose=verbose)

        for mol in integrals.keys():
            title = mol + ', cycle=' + str(cycle) + ', U=' + str(V[-1])
            if verbose:
                print('working on: ' + str(mol))
            x, y = get_flux(on_data, tspan=tspan, mol=mol, removebackground=True,
                            unit='nmol/s', verbose=verbose)

            if type(integrals[mol]) is dict:
                ts = t_steady[mol]
                if plottransient:
                    ax='new'
                else:
                    ax=None
                ss, dyn = integrate_transient(x, y, tspan=tspan, t_steady=ts,
                                              ax=ax, title=title, verbose=verbose)
                integrals[mol]['ss'] += [ss]
                integrals[mol]['dyn'] += [dyn]
            else:
                integrals[mol] += [np.trapz(y, x)]
    integrals['V'] = V
    if verbose:
        print('\nfunction \'get_datapoints\' finished!\n\n')
    return integrals



def integrate_transient(x, y, tspan=None, t_transient=None, t_steady='half',
                        ax=None, title=None, colors=['r', 'b', 'g'],
                        verbose=True):
    '''
    This will return seperate values for the transients and steady-states of a
    a certain compound, based on extrapolating the average signal after t_transient
    to the interval before t_transient and subtracting.
    '''
    if ax == 'new':
        fig = plt.figure()
        ax = fig.add_subplot(111)

    if tspan is None:
        tspan = [x[0], x[-1]]
    '''
    if t_transient is None:
        t_transient = tspan
    elif t_transient == 'half':
        t_transient = [tspan[0], (tspan[0] + tspan[-1])/2]
    '''
    if t_steady == 'half':
        t_steady = [(tspan[0] + tspan[-1])/2, tspan[1]]

    I_int = [I for (I, x_I) in enumerate(x) if tspan[0]<=x_I<=tspan[-1]]
#    I_transient = [I for (I, x_I) in enumerate(x) if t_transient[0]<=x_I<=t_transient[-1]]
    I_steady = [I for (I, x_I) in enumerate(x) if t_steady[0]<x_I<=t_steady[-1]]

    x_int = x[I_int]
    y_int = y[I_int]
#    x_transient = x[I_transient]
#    y_transient = y[I_steady]
    x_steady = x[I_steady]
    y_steady = y[I_steady]

    base = np.trapz(y_steady, x_steady) / (x_steady[-1] - x_steady[0])

    y_zero = np.zeros(np.shape(x_int))
    y_base = y_zero + base
    y_s = np.minimum(y_int, base)
    y_t = np.maximum(y_int-base, 0)

    steady = np.trapz(y_s, x_int)
    transient = np.trapz(y_t, x_int)

    if ax is not None:
        ax.fill_between(x_int, y_int, y_zero, where=y_int>y_zero,
                facecolor=colors[1], interpolate=True)
        ax.fill_between(x_int, y_int, y_base, where=y_int>y_base,
                facecolor=colors[2], interpolate=True)
        ax.plot(x, y, color=colors[0])
        if title is not None:
            ax.set_title(title)

    if verbose:
        if title is not None:
            print(title)
        print('\tsteady = ' + str(steady) + '\n\ttransient = ' + str(transient))

    return steady, transient




def activity_steps(data, mols, cycles, cycle_str='selector',
                   mode='average', t_int=15, t_tail=30, t_pre=15,
                   background=None, t_bg=None, unit='pmol/s',
                   ax='new', tspan_plot=None, verbose=True,
                   ):
    if verbose:
        print('\n\nfunction \'evaluate_datapoints\' at your service!\n')
    # ----- parse inputs -------- #
    mdict = dict([(m.name, m) for m in mols])

    if mode in ['average', 'averaging', 'mean']:
        mode = 'average'
    elif mode in ['integral', 'integrate', 'integrating']:
        mode = 'integral'

    if t_bg is not None:
        bgs = {}
        for mol, m in mdict.items():
            x_bg, y_bg = m.get_flux(data, tspan=t_bg, removebackground=False, unit=unit)
            bgs[mol] = np.mean(y_bg)
    # should perhaps give additional options for bg, but honostly t_bg is pretty good
    else:
        bgs = dict([(mol, 0) for mol in mdict.keys()])

    if ax=='new':
        ax = plot_experiment(data, mols=mols, removebackground=False,
                             tspan=tspan_plot, emphasis=None)

    Qs, Vs = np.array([]), np.array([])
    ns = dict([(mol, np.array([])) for mol in mdict.keys()])
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

        t_v, v = get_potential(c, tspan=tspan, verbose=verbose)
        V = np.mean(v)
        Vs = np.append(Vs, V)

        t, I = get_current(c, tspan=tspan, verbose=verbose)
        if mode == 'average':
            Q = np.mean(I)
        elif mode == 'integral':
            Q = np.trapz(I, t)
        Qs = np.append(Qs, Q)

        for mol, m in mdict.items():
            x, y0 = m.get_flux(c, tspan=tspan, unit=unit, verbose=verbose)
            bg = bgs[mol]
            y = y0 - bg
            if mode == 'average':
                yy = np.mean(y)
            elif mode == 'integra':
                yy = np.trapz(y, x)
            ns[mol] = np.append(ns[mol], yy)
            if ax is not None:
                try:
                    iter(bg)
                except TypeError:
                    bg = bg * np.ones(y0.shape)
                color = m.get_color()
                ax[0].fill_between(x, y0, bg, where=y0>bg, color=color, alpha=0.5)
        if ax is not None:
            ax[1].plot(t_v, v, 'k-', linewidth=3)
            J = I * 1e3 / data['A_el']
            bg_J = np.zeros(J.shape)
            ax[2].fill_between(t, J, bg_J, color='0.5', alpha=0.5)


    if verbose:
        print('\nfunction \'evaluate_datapoints\' finished!\n\n')

    return {'Qs':Qs, 'ns':ns, 'Vs':Vs, 'ax':ax}

