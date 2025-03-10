# -*- coding: utf-8 -*-
"""
Created on Fri Nov  5 01:57:46 2021

@author: yrc2
"""
import os
import numpy as np
import pandas as pd
import biosteam as bst
from .biorefinery import Biorefinery
from biorefineries import cane
from biorefineries.tea.cellulosic_ethanol_tea import foc_table, capex_table
from thermosteam.utils import array_roundsigfigs

__all__ = (
    'save_system_reports',
    'save_detailed_expenditure_tables',
    'save_detailed_life_cycle_tables',  
    'save_YRCP2023_distribution_table',
)

def save_system_reports():
    cane.YRCP2023
    folder = os.path.dirname(__file__)
    folder = os.path.join(folder, 'results')
    for i, name in (('O7.WT', 'DC_sugarcane_to_biodiesel'),
                    ('O8.WT', 'ICFR_sugarcane_to_biodiesel'),
                    ('O9.WT', 'ICF_sugarcane_to_biodiesel')):
        br = cane.Biorefinery(i)
        filename = name + '_detailed_report.xlsx'
        file = os.path.join(folder, filename)
        br.sys.save_report(file)

def save_detailed_expenditure_tables(sigfigs=3, product=None):
    folder = os.path.dirname(__file__)
    folder = os.path.join(folder, 'results')
    filename = 'expenditures.xlsx'
    file = os.path.join(folder, filename)
    writer = pd.ExcelWriter(file)
    if product is None: product = 'biodiesel'
    
    def get_sys(name):
        brf = Biorefinery(name, update_feedstock_price=False)
        try: brf.biodiesel.ID = 'biomass_based_diesel'
        except: pass   
        try: brf.FGD_lime.ID = 'flue_gas_desulfurization_lime'
        except: pass
        return brf.sys
    
    def get_tea(name):
        brf = Biorefinery(name, update_feedstock_price=False)
        return brf.tea
    if product == 'biodiesel':
        cane.YRCP2023()
        IDs = (
            'O7.WT',
            'O9.WT',
            'O8.WT',
        )
        names = [
            'DC',
            'ICF',
            'ICFR',
        ]
        product_IDs = [
            'cellulosic_based_diesel',
            'biomass_based_diesel'
        ]
    else:
        IDs = (
            'S1',
            'S2', 
            'O1', 
            'O2'
        )
        product_IDs = [
            'advanced_ethanol', 
            'cellulosic_ethanol'
        ]
    syss = [get_sys(i) for i in IDs]
    teas = [get_tea(i) for i in IDs]
    tables = {
        'VOC': bst.report.voc_table(syss, product_IDs, names, with_products=True),
        'FOC': foc_table(teas, names),
        'CAPEX': capex_table(teas, names),
    }
    for key, table in tables.items(): 
        values = array_roundsigfigs(table.values, sigfigs=3, inplace=True)
        if key == 'CAPEX': # Bug in pandas
            for i, col in enumerate(table):
                table[col] = values[:, i]
        # if key == 'VOC':
        #     new_index = sorted(
        #         table.index, 
        #         key=lambda x: -abs(table.loc[x][1:].sum()) if x[0] == 'Raw materials' else 0,
        #     )
        #     tables[key] = table.reindex(new_index)
        table.to_excel(writer, key)
    writer.close()
    return tables
    
def save_detailed_life_cycle_tables(sigfigs=3, product=None):
    if product is None:
        product = 'biodiesel'
    def get(configuration, name, RIN=False):
        brf = Biorefinery(configuration)
        return getattr(brf, name)

    GWP = cane.biorefinery.GWP
    bst.settings.define_impact_indicator(GWP, 'kg*CO2e')
    folder = os.path.dirname(__file__)
    folder = os.path.join(folder, 'results')
    filename = 'life_cycle.xlsx'
    file = os.path.join(folder, filename)
    writer = pd.ExcelWriter(file)
    index = ['Energy allocation',
             'Economic allocation',
             'Displacement allocation']
    if product == 'biodiesel':
        cane.YRCP2023()
        IDs = ('O7.WT', 'O9.WT', 'O8.WT')
        def redistribute_streams(ID):
            cbd, bbd = get(ID, 'cellulosic_based_diesel'), get(ID, 'biomass_based_diesel')
            bbd.set_CF(GWP, 0)
            cbd.set_CF(GWP, 0)
            return (cbd, bbd)
        streams = [redistribute_streams(i) for i in IDs]
        columns = [
            'DC [kg∙CO2e∙kg-1]',
            'ICF [kg∙CO2e∙kg-1]',
            'ICFR [kg∙CO2e∙kg-1]',
        ]
    elif product == 'ethanol':
        IDs = ('S1', 'S2', 'O1', 'O2')
        streams = [(get(i, 'advanced_ethanol'), get(i, 'cellulosic_ethanol')) for i in IDs]
        columns = [
            'Sugarcane E-DC [kg∙CO2e∙kg-1]',
            'Sugarcane E-ICF [kg∙CO2e∙kg-1]',
            'Oilcane EB-DC [kg∙CO2e∙kg-1]',
            'Oilcane EB-ICF [kg∙CO2e∙kg-1]',
        ]
    else:
        raise ValueError(f"product '{product}' is not valid; valid options include 'biodiesel' and 'ethanol'")
    names = [i.split(' [')[0] for i in columns]
    methods = (f'GWP_{product}_allocation', f'GWP_{product}', f'GWP_{product}_displacement')
    syss = [get(i, 'sys') for i in IDs]
    values = np.zeros([len(methods), len(IDs)])
    for i, method in enumerate(methods):
        for j, name in enumerate(IDs):
            brf = Biorefinery(name)
            values[i, j] = getattr(brf, method)() 
    df_gwp = pd.DataFrame(values, index=index, columns=columns)
    tables = {
        'Inventory': bst.report.lca_inventory_table(
            syss, GWP, streams, names
        ),
        'Displacement allocation': bst.report.lca_displacement_allocation_table(
            syss, GWP, streams, product, names
        ),
        'Energy allocation factors': bst.report.lca_property_allocation_factor_table(
            syss, property='energy', basis='GGE', system_names=names, groups=('ethanol',),
        ),
        'Economic allocation factors': bst.report.lca_property_allocation_factor_table(
            syss, property='revenue', basis='USD', system_names=names, groups=('ethanol',),
        ),
        'Displacement allocation factors': bst.report.lca_displacement_allocation_factor_table(
            syss, streams, GWP, names, groups=('ethanol',),
        ),
        f'GWP {product}': df_gwp,
    }
    for key, table in tables.items(): 
        array_roundsigfigs(table.values, sigfigs=3, inplace=True)
        table.to_excel(writer, key) 
    writer.close()
    return tables

def save_YRCP2023_distribution_table():
    folder = os.path.dirname(__file__)
    folder = os.path.join(folder, 'results')
    filename = 'parameters.xlsx'
    file = os.path.join(folder, filename)
    table = cane.get_YRCP2023_distribution_table() 
    table.to_excel(file)
    return table