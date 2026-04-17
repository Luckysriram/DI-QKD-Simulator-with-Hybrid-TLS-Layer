"""
ns3_real — Real NS-3 Simulation Package
========================================
Drop-in addition to the existing ns3_sim/ Python-only module.
Routes computation through real NS-3 C++ via WSL.

Modules:
    ns3_bridge      — Windows ↔ WSL ↔ NS-3 interface
    ns3_visualizer  — Publication-quality plots from NS-3 output
"""

from ns3_real.ns3_bridge import NS3Bridge

__all__ = ["NS3Bridge"]
__version__ = "1.0.0"
