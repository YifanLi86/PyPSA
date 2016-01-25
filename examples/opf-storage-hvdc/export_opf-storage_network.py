
#This script builds a network manually using network.add, so that it
#has two 3-bus disconnected AC networks, connected by HVDC
#links. Storage and generation (wind and gas) is then optimised.

#The network is then written as CSV files to csv_folder_name.


# make the code as Python 3 compatible as possible
from __future__ import print_function, division
from __future__ import absolute_import

import pypsa

import datetime
import pandas as pd

import networkx as nx

import numpy as np

from itertools import chain

import inspect

import os
from six.moves import range



#ensure the same random number are produced when refactoring
np.random.seed(1)



csv_folder_name = 'opf-storage-data'



#Build the Network object, which stores all other objects

network = pypsa.Network()

#Build the snapshots we consider for the first T hours in 2015

T = 12

network.set_snapshots(pd.to_datetime([datetime.datetime(2015,1,1) + datetime.timedelta(hours=i) for i in range(T)]))

#let each snapshot represent 3 hours
network.snapshot_weightings = pd.Series(3.,index=network.snapshots)

print("network:",network)
print("snapshots:",network.snapshots)


#add fuel types
network.add("Source","gas",co2_emissions=0.24)
network.add("Source","wind")
network.add("Source","battery")


# in kg CO2e
network.co2_limit = 1000


#The network is two three-node AC networks connected by 2 point-to-point DC links

#building block
n = 3

#copies
c = 2


#add buses
for i in range(n*c):
    network.add("Bus",i,v_nom="380")

#add lines
for i in range(n*c):
    network.add("Line",i,
                bus0=str(i),
                bus1=str(n*(i // n)+ (i+1) % n),
                x=np.random.random(),
                s_nom=0,
                capital_cost=0.2*np.random.random(),
                s_nom_min=0,
                s_nom_extendable=True)

#make one line non-extendable
network.lines.at["2","s_nom"] = 200.
network.lines.at["2","s_nom_extendable"] = False

#add HVDC lines
for i in range(2):
    network.add("TransportLink","TL %d" % (i),
                bus0=str(i),
                bus1=str(3+i),
                p_nom=1000,
                p_max=900,
                p_min=-900,
                s_nom=0,
                capital_cost=0.2*np.random.random(),
                s_nom_min=0,
                s_nom_extendable=True)


#make one HVDC non-extendable
network.transport_links.at["TL 1","s_nom"] = 300.
network.transport_links.at["TL 1","s_nom_extendable"] = False


#add loads
for i in range(n*c):
    network.add("Load",i,bus=str(i))

#add some generators
for i in range(n*c):
    #storage
    network.add("StorageUnit","Storage %d" % (i),
                bus=str(i),
                p_nom=0,source="battery",
                marginal_cost=4*np.random.random(),
                capital_cost=1000*np.random.random(),
                p_nom_extendable=True,
                p_max_pu_fixed=1,
                p_min_pu_fixed=-1,
                efficiency_store=0.9,
                efficiency_dispatch=0.95,
                standing_loss=0.01,
                max_hours=6)
    #wind generator
    network.add("Generator","Wind %d" % (i),bus=str(i),
                p_nom=100,source="wind",dispatch="variable",
                marginal_cost=0 + 0.01*np.random.random(), #non-zero marginal cost ensures unique optimisation result
                capital_cost=2000 + 1000*np.random.random(),
                p_nom_extendable=True,
                p_nom_max=np.nan,
                p_nom_min=100)
    #gas generator
    network.add("Generator","Gas %d" % (i),bus=str(i),
                p_nom=0,source="gas",dispatch="flexible",
                marginal_cost=2 + 4*np.random.random(),
                capital_cost=100 + 100*np.random.random(),
                efficiency=0.35 + 0.01*np.random.random(),
                p_max_pu_fixed = 0.85,
                p_min_pu_fixed = 0.02,
                p_nom_extendable=True,
                p_nom_max=np.nan,
                p_nom_min=0)

#make some objects non-extendable - useful for unit testing
network.generators.at["Gas 0","p_nom"] = 350
network.generators.at["Gas 0","p_nom_extendable"] = False

network.generators.at["Wind 2","p_nom"] = 150
network.generators.at["Wind 2","p_nom_extendable"] = False

network.storage_units.at["Storage 1","p_nom"] = 25
network.storage_units.at["Storage 1","p_nom_extendable"] = False


#now attach some time series

network.loads.p_set = pd.DataFrame(index = network.snapshots,
                                   columns = network.loads.index,
                                   data = 1000*np.random.rand(len(network.snapshots), len(network.loads)))


wind_generators = network.generators[network.generators.source == "wind"]

network.generators.p_max_pu.loc[:,wind_generators.index] = pd.DataFrame(index = network.snapshots,
                                                                        columns = wind_generators.index,
                                                                        data = np.random.rand(len(network.snapshots), len(wind_generators)))

network.generators.p_set.loc[:,wind_generators.index] = network.generators.p_max_pu.loc[:,wind_generators.index].multiply(network.generators.p_nom,axis=1)

network.storage_units.state_of_charge_initial = 0.0

#make the storage more complicated
network.storage_units.at["Storage 2","cyclic_state_of_charge"] = True
network.storage_units.at["Storage 4","cyclic_state_of_charge"] = True


network.storage_units.state_of_charge_set.at[network.snapshots[3],"Storage 3"] = 50.


network.storage_units.state_of_charge_set.at[network.snapshots[2],"Storage 4"] = 25.


time_series = {"generators" : {"p_max_pu" : lambda g: g.dispatch == "variable"},
               "loads" : {"p_set" : None},
               "storage_units" : {"state_of_charge_set" : None},
}


network.name = "Test 6 bus"

network.export_to_csv_folder(csv_folder_name,time_series)