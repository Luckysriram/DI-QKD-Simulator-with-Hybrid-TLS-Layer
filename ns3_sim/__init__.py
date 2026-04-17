"""
NS-3 Network Simulation Module for DI-QKD Simulator

Provides quantum and classical channel models, network topologies,
and simulation scenarios for testing QKD + TLS under realistic
network conditions.
"""

from ns3_sim.channel_model import QuantumChannel, ClassicalChannel, EavesdropperChannel
from ns3_sim.topology import QKDTopology
from ns3_sim.scenarios import get_scenario, list_scenarios

__version__ = "1.0.0"
__all__ = [
    "QuantumChannel", "ClassicalChannel", "EavesdropperChannel",
    "QKDTopology", "get_scenario", "list_scenarios",
]
