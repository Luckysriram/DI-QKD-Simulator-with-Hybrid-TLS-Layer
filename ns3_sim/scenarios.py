"""
Pre-built Simulation Scenarios

Ready-to-run scenarios for common QKD deployment configurations:
- Short-distance metro fiber (10 km)
- Inter-city fiber (100 km)
- LEO satellite link
- Eavesdropper attack
- Distance sweep (for plotting key rate vs distance)
"""

from typing import Dict, Any, List, Optional

from ns3_sim.topology import QKDTopology, NodeType
from ns3_sim.channel_model import QuantumChannel, EavesdropperChannel


SCENARIOS = {}


def _register(name: str, description: str):
    """Decorator to register a scenario."""
    def decorator(func):
        SCENARIOS[name] = {
            'function': func,
            'description': description,
        }
        return func
    return decorator


@_register("fiber_10km", "Short-distance metro fiber QKD (10 km)")
def fiber_10km() -> Dict[str, Any]:
    """Short metro-distance QKD over fiber."""
    topo = QKDTopology.create_point_to_point(distance_km=10.0, name="fiber_10km")
    return {
        'topology': topo,
        'qkd_params': {'key_size': 512, 'chsh_rounds': 1000},
        'tls_params': {'include_qkd': True, 'data_size_bytes': 10000},
        'description': 'Metro fiber: 10 km, low loss (2 dB), standard detectors',
    }


@_register("fiber_50km", "Medium-distance fiber QKD (50 km)")
def fiber_50km() -> Dict[str, Any]:
    """Medium-distance QKD over fiber."""
    topo = QKDTopology.create_point_to_point(distance_km=50.0, name="fiber_50km")
    return {
        'topology': topo,
        'qkd_params': {'key_size': 1024, 'chsh_rounds': 2000},
        'tls_params': {'include_qkd': True, 'data_size_bytes': 10000},
        'description': 'Intercity fiber: 50 km, 10 dB loss',
    }


@_register("fiber_100km", "Long-distance fiber QKD (100 km)")
def fiber_100km() -> Dict[str, Any]:
    """Long-distance QKD — pushing the limits of direct fiber."""
    topo = QKDTopology.create_point_to_point(distance_km=100.0, name="fiber_100km")
    return {
        'topology': topo,
        'qkd_params': {'key_size': 2048, 'chsh_rounds': 5000},
        'tls_params': {'include_qkd': True, 'data_size_bytes': 5000},
        'description': 'Long fiber: 100 km, 20 dB loss — near detection limit',
    }


@_register("satellite_leo", "LEO satellite QKD link (600 km free-space)")
def satellite_leo() -> Dict[str, Any]:
    """
    Low Earth Orbit satellite QKD link.
    Free-space channels have much lower loss than fiber at long distances.
    """
    topo = QKDTopology(name="satellite_leo")
    topo.add_node("ground_alice", NodeType.ALICE, position_km=0.0)
    topo.add_node("satellite", NodeType.RELAY, position_km=600.0)
    topo.add_node("ground_bob", NodeType.BOB, position_km=1200.0)
    
    # Uplink: ground → satellite (free-space, ~10 dB total loss)
    topo.add_link("ground_alice", "satellite", distance_km=600.0,
                  quantum_params={
                      'attenuation_db_per_km': 0.017,  # Free-space ~10 dB total
                      'detector_efficiency': 0.3,        # Better detectors in space
                      'depolarization_rate': 0.001,      # Less depolarization
                  })
    
    # Downlink: satellite → ground
    topo.add_link("satellite", "ground_bob", distance_km=600.0,
                  quantum_params={
                      'attenuation_db_per_km': 0.017,
                      'detector_efficiency': 0.1,
                      'depolarization_rate': 0.001,
                  })
    
    return {
        'topology': topo,
        'qkd_params': {'key_size': 1024, 'chsh_rounds': 2000},
        'tls_params': {'include_qkd': True, 'data_size_bytes': 10000},
        'description': 'LEO satellite: 600 km uplink + 600 km downlink, free-space optics',
    }


@_register("eve_attack", "Eavesdropper attack scenario")
def eve_attack(
    distance_km: float = 20.0,
    intercept_rate: float = 0.5
) -> Dict[str, Any]:
    """Eve intercept-resend attack on a fiber link."""
    topo = QKDTopology.create_with_eve(
        distance_km=distance_km,
        intercept_rate=intercept_rate,
        name="eve_attack"
    )
    return {
        'topology': topo,
        'qkd_params': {'key_size': 512, 'chsh_rounds': 1000},
        'tls_params': {'include_qkd': True, 'data_size_bytes': 10000},
        'description': f'Eavesdropper: {intercept_rate:.0%} intercept rate at {distance_km/2} km',
    }


@_register("distance_sweep", "Key rate vs distance analysis")
def distance_sweep(
    distances: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Generate topologies for a range of distances to analyze
    key rate decay with fiber length.
    """
    if distances is None:
        distances = [1, 5, 10, 20, 30, 50, 75, 100, 150, 200]
    
    topologies = []
    for dist in distances:
        topo = QKDTopology.create_point_to_point(
            distance_km=dist,
            name=f"sweep_{dist}km"
        )
        topologies.append({
            'distance_km': dist,
            'topology': topo,
        })
    
    return {
        'topologies': topologies,
        'distances': distances,
        'qkd_params': {'key_size': 512, 'chsh_rounds': 1000},
        'description': f'Distance sweep: {len(distances)} points from {distances[0]} to {distances[-1]} km',
    }


@_register("metro_ring", "Metro ring network (4 nodes)")
def metro_ring() -> Dict[str, Any]:
    """Metro-area ring topology with 4 nodes."""
    topo = QKDTopology.create_metro_ring(num_nodes=4, ring_circumference_km=40.0)
    return {
        'topology': topo,
        'qkd_params': {'key_size': 256, 'chsh_rounds': 500},
        'tls_params': {'include_qkd': True, 'data_size_bytes': 5000},
        'description': 'Metro ring: 4 nodes, 40 km circumference, 10 km per segment',
    }


def get_scenario(name: str, **kwargs) -> Dict[str, Any]:
    """
    Get a scenario by name.
    
    Args:
        name: Scenario name
        **kwargs: Additional parameters for the scenario
    
    Returns:
        Scenario configuration dict
    """
    if name not in SCENARIOS:
        raise ValueError(
            f"Unknown scenario '{name}'. Available: {list(SCENARIOS.keys())}"
        )
    return SCENARIOS[name]['function'](**kwargs)


def list_scenarios() -> List[Dict[str, str]]:
    """List all available scenarios."""
    return [
        {'name': name, 'description': info['description']}
        for name, info in SCENARIOS.items()
    ]
