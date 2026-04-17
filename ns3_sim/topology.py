"""
QKD Network Topology

Defines network topologies with Alice, Bob, Eve nodes
connected via quantum and classical channels.
Provides NS-3-compatible discrete-event simulation.
"""

import time
import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum

from ns3_sim.channel_model import QuantumChannel, ClassicalChannel, EavesdropperChannel


class NodeType(Enum):
    """Types of nodes in the QKD network."""
    ALICE = "alice"
    BOB = "bob"
    EVE = "eve"
    KMS = "kms"          # Key Management Server
    RELAY = "relay"       # Trusted relay node
    ROUTER = "router"     # Classical router


@dataclass
class NetworkNode:
    """A node in the QKD network."""
    name: str
    node_type: NodeType
    position_km: float = 0.0
    
    # Node state
    key_buffer: List[int] = field(default_factory=list)
    is_active: bool = True
    
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'type': self.node_type.value,
            'position_km': self.position_km,
            'key_buffer_size': len(self.key_buffer),
            'active': self.is_active,
        }


@dataclass
class NetworkLink:
    """A link between two nodes."""
    node_a: str
    node_b: str
    quantum_channel: Optional[QuantumChannel] = None
    classical_channel: Optional[ClassicalChannel] = None
    
    def to_dict(self) -> dict:
        info = {
            'endpoints': [self.node_a, self.node_b],
        }
        if self.quantum_channel:
            info['quantum'] = self.quantum_channel.get_info()
        if self.classical_channel:
            info['classical'] = self.classical_channel.get_info()
        return info


class QKDTopology:
    """
    QKD Network Topology.
    
    Manages nodes and links for simulating quantum key distribution
    over realistic network configurations.
    
    Supports:
    - Point-to-point (Alice ↔ Bob)
    - Point-to-point with Eve
    - Star topology (multiple users → central KMS)
    - Metro ring topology
    """
    
    def __init__(self, name: str = "default"):
        self.name = name
        self.nodes: Dict[str, NetworkNode] = {}
        self.links: List[NetworkLink] = {}
        self._event_queue: List[Tuple[float, str, dict]] = []
        self._current_time_ms = 0.0
    
    # ── Node management ──────────────────────────────────────────────
    
    def add_node(
        self,
        name: str,
        node_type: NodeType,
        position_km: float = 0.0
    ) -> NetworkNode:
        """Add a node to the topology."""
        node = NetworkNode(name=name, node_type=node_type, position_km=position_km)
        self.nodes[name] = node
        return node
    
    def get_node(self, name: str) -> NetworkNode:
        """Get a node by name."""
        if name not in self.nodes:
            raise KeyError(f"Node '{name}' not found")
        return self.nodes[name]
    
    # ── Link management ──────────────────────────────────────────────
    
    def add_link(
        self,
        node_a: str,
        node_b: str,
        distance_km: Optional[float] = None,
        quantum_params: Optional[dict] = None,
        classical_params: Optional[dict] = None
    ) -> NetworkLink:
        """
        Add a link between two nodes with quantum and classical channels.
        
        Args:
            node_a: First node name
            node_b: Second node name
            distance_km: Link distance (auto-calculated from positions if None)
            quantum_params: Additional quantum channel parameters
            classical_params: Additional classical channel parameters
        """
        if node_a not in self.nodes:
            raise KeyError(f"Node '{node_a}' not found")
        if node_b not in self.nodes:
            raise KeyError(f"Node '{node_b}' not found")
        
        if distance_km is None:
            pos_a = self.nodes[node_a].position_km
            pos_b = self.nodes[node_b].position_km
            distance_km = abs(pos_b - pos_a)
        
        qc_params = {'distance_km': distance_km}
        if quantum_params:
            qc_params.update(quantum_params)
        
        cc_params = {'distance_km': distance_km}
        if classical_params:
            cc_params.update(classical_params)
        
        link = NetworkLink(
            node_a=node_a,
            node_b=node_b,
            quantum_channel=QuantumChannel(**qc_params),
            classical_channel=ClassicalChannel(**cc_params),
        )
        
        link_key = f"{node_a}-{node_b}"
        self.links[link_key] = link
        return link
    
    def add_eve_link(
        self,
        node_a: str,
        node_b: str,
        eve_name: str = "eve",
        distance_km: Optional[float] = None,
        eve_position_km: Optional[float] = None,
        intercept_rate: float = 0.5,
        classical_params: Optional[dict] = None
    ) -> NetworkLink:
        """
        Add a link with an eavesdropper (Eve) tapping the quantum channel.
        """
        if distance_km is None:
            pos_a = self.nodes[node_a].position_km
            pos_b = self.nodes[node_b].position_km
            distance_km = abs(pos_b - pos_a)
        
        if eve_position_km is None:
            eve_position_km = distance_km / 2
        
        cc_params = {'distance_km': distance_km}
        if classical_params:
            cc_params.update(classical_params)
        
        link = NetworkLink(
            node_a=node_a,
            node_b=node_b,
            quantum_channel=EavesdropperChannel(
                distance_km=distance_km,
                eve_position_km=eve_position_km,
                intercept_rate=intercept_rate,
            ),
            classical_channel=ClassicalChannel(**cc_params),
        )
        
        link_key = f"{node_a}-{node_b}"
        self.links[link_key] = link
        return link
    
    def get_link(self, node_a: str, node_b: str) -> NetworkLink:
        """Get the link between two nodes."""
        key = f"{node_a}-{node_b}"
        if key in self.links:
            return self.links[key]
        key = f"{node_b}-{node_a}"
        if key in self.links:
            return self.links[key]
        raise KeyError(f"No link between '{node_a}' and '{node_b}'")
    
    # ── Topology builders ────────────────────────────────────────────
    
    @classmethod
    def create_point_to_point(
        cls,
        distance_km: float = 10.0,
        name: str = "p2p"
    ) -> 'QKDTopology':
        """Create a simple Alice ↔ Bob point-to-point topology."""
        topo = cls(name=name)
        topo.add_node("alice", NodeType.ALICE, position_km=0.0)
        topo.add_node("bob", NodeType.BOB, position_km=distance_km)
        topo.add_link("alice", "bob", distance_km=distance_km)
        return topo
    
    @classmethod
    def create_with_eve(
        cls,
        distance_km: float = 10.0,
        eve_position_km: Optional[float] = None,
        intercept_rate: float = 0.5,
        name: str = "p2p_eve"
    ) -> 'QKDTopology':
        """Create Alice ↔ Bob with Eve eavesdropping."""
        topo = cls(name=name)
        
        if eve_position_km is None:
            eve_position_km = distance_km / 2
        
        topo.add_node("alice", NodeType.ALICE, position_km=0.0)
        topo.add_node("eve", NodeType.EVE, position_km=eve_position_km)
        topo.add_node("bob", NodeType.BOB, position_km=distance_km)
        
        topo.add_eve_link(
            "alice", "bob",
            eve_name="eve",
            distance_km=distance_km,
            eve_position_km=eve_position_km,
            intercept_rate=intercept_rate,
        )
        return topo
    
    @classmethod
    def create_star(
        cls,
        num_users: int = 4,
        distances_km: Optional[List[float]] = None,
        name: str = "star"
    ) -> 'QKDTopology':
        """Create a star topology with a central KMS."""
        topo = cls(name=name)
        
        if distances_km is None:
            distances_km = [10.0 + i * 5 for i in range(num_users)]
        
        topo.add_node("kms", NodeType.KMS, position_km=0.0)
        
        for i in range(num_users):
            user_name = f"user_{i}"
            dist = distances_km[i] if i < len(distances_km) else 10.0
            angle_rad = 2 * 3.14159 * i / num_users
            topo.add_node(user_name, NodeType.ALICE, position_km=dist)
            topo.add_link("kms", user_name, distance_km=dist)
        
        return topo
    
    @classmethod
    def create_metro_ring(
        cls,
        num_nodes: int = 4,
        ring_circumference_km: float = 40.0,
        name: str = "metro_ring"
    ) -> 'QKDTopology':
        """Create a metro ring topology."""
        topo = cls(name=name)
        
        segment_km = ring_circumference_km / num_nodes
        
        for i in range(num_nodes):
            node_type = NodeType.ALICE if i == 0 else (
                NodeType.BOB if i == num_nodes - 1 else NodeType.RELAY
            )
            topo.add_node(f"node_{i}", node_type, position_km=i * segment_km)
        
        for i in range(num_nodes):
            next_i = (i + 1) % num_nodes
            topo.add_link(f"node_{i}", f"node_{next_i}", distance_km=segment_km)
        
        return topo
    
    # ── Discrete-event simulation ────────────────────────────────────
    
    def schedule_event(self, time_ms: float, event_type: str, data: dict = None):
        """Schedule an event in the simulation."""
        self._event_queue.append((time_ms, event_type, data or {}))
        self._event_queue.sort(key=lambda x: x[0])
    
    def run_simulation(self, duration_ms: float = 10000.0) -> List[dict]:
        """
        Run a basic discrete-event simulation.
        
        Returns:
            List of event results
        """
        results = []
        self._current_time_ms = 0.0
        
        while self._event_queue and self._current_time_ms < duration_ms:
            event_time, event_type, data = self._event_queue.pop(0)
            self._current_time_ms = event_time
            
            result = {
                'time_ms': event_time,
                'type': event_type,
                'data': data,
            }
            results.append(result)
        
        return results
    
    # ── Info ──────────────────────────────────────────────────────────
    
    def get_topology_info(self) -> dict:
        """Get complete topology information."""
        return {
            'name': self.name,
            'num_nodes': len(self.nodes),
            'num_links': len(self.links),
            'nodes': {k: v.to_dict() for k, v in self.nodes.items()},
            'links': {k: v.to_dict() for k, v in self.links.items()},
        }
    
    def reset_metrics(self):
        """Reset all channel metrics."""
        for link in self.links.values():
            if link.quantum_channel:
                link.quantum_channel.reset_metrics()
            if link.classical_channel:
                link.classical_channel.reset_metrics()
    
    def __repr__(self) -> str:
        return (
            f"QKDTopology(name='{self.name}', "
            f"nodes={len(self.nodes)}, links={len(self.links)})"
        )
