"""
DI-QKD TLS + NS-3 Network Simulation Demo

Demonstrates the full quantum-secured communication stack:
1. NS-3 network simulation with quantum/classical channels
2. QKD key generation over simulated fiber
3. Triple-hybrid TLS handshake (ECDH + ML-KEM-768 + QKD)
4. Encrypted data transfer analysis
5. Eavesdropper detection scenario
6. Distance sweep analysis with visualization
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

from ns3_sim.channel_model import QuantumChannel, ClassicalChannel, EavesdropperChannel
from ns3_sim.topology import QKDTopology
from ns3_sim.qkd_application import QKDApplication
from ns3_sim.tls_application import TLSApplication
from ns3_sim.scenarios import get_scenario, list_scenarios
from ns3_sim.metrics import MetricsCollector
from ns3_sim.visualizer import (
    plot_key_rate_vs_distance, plot_qber_vs_distance,
    plot_tls_handshake_breakdown, plot_eve_detection,
    HAS_MATPLOTLIB
)


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_metric(label: str, value, unit: str = ""):
    print(f"  {label:30s}: {value} {unit}")


def demo_1_channel_models():
    """Demo 1: Quantum and Classical Channel Models"""
    print_header("Demo 1: Channel Models")
    
    distances = [1, 10, 50, 100, 200]
    print(f"  {'Distance':>10s}  {'Trans. Prob':>12s}  {'QBER':>8s}  {'Key Rate':>12s}")
    print(f"  {'-'*10}  {'-'*12}  {'-'*8}  {'-'*12}")
    
    for dist in distances:
        qc = QuantumChannel(distance_km=dist)
        print(f"  {dist:>8.0f} km  "
              f"{qc.transmission_probability:>12.8f}  "
              f"{qc.expected_qber:>8.4f}  "
              f"{qc.key_rate_per_pulse:>12.8f}")
    
    print(f"\n  Classical Channel (10 km):")
    cc = ClassicalChannel(distance_km=10.0, bandwidth_mbps=1000)
    delivered, latency = cc.transmit_reliable(1000)
    print_metric("Latency", f"{latency:.4f}", "ms")
    print_metric("Bandwidth", cc.bandwidth_mbps, "Mbps")


def demo_2_qkd_over_fiber():
    """Demo 2: QKD Protocol over Simulated Fiber"""
    print_header("Demo 2: QKD over 10 km Fiber")
    
    scenario = get_scenario("fiber_10km")
    topo = scenario['topology']
    app = QKDApplication(topo)
    
    result = app.run_bb84_over_channel("alice-bob", key_size=512)
    
    print_metric("Distance", f"{result['distance_km']}", "km")
    print_metric("Photons sent", result['key_size_requested'])
    print_metric("Photons detected", result['photons_detected'])
    print_metric("Detection rate", f"{result['detection_rate']:.2%}")
    print_metric("Sifted key length", f"{result['sifted_key_length']} bits")
    print_metric("Final key length", f"{result['final_key_length']} bits")
    print_metric("Effective QBER", f"{result['effective_qber']:.4f}")
    print_metric("Secure", "✓ YES" if result['is_secure'] else "✗ NO")
    
    # Also run CHSH
    chsh = app.run_chsh_over_channel("alice-bob", num_rounds=1000)
    print(f"\n  CHSH Bell Test:")
    print_metric("Effective CHSH value", f"{chsh['effective_chsh_value']:.4f}")
    print_metric("Bell violation", "✓ YES" if chsh['violates_bell'] else "✗ NO")
    print_metric("Device-independent", "✓" if chsh['device_independent'] else "✗")


def demo_3_tls_handshake():
    """Demo 3: TLS Handshake Timing Analysis"""
    print_header("Demo 3: Hybrid TLS Handshake Simulation")
    
    topo = QKDTopology.create_point_to_point(distance_km=10.0)
    app = TLSApplication(topo)
    
    # With QKD
    result_qkd = app.simulate_handshake("alice-bob", include_qkd=True)
    
    print(f"  Triple-Hybrid Handshake (ECDH + ML-KEM + QKD):")
    print_metric("Total handshake time", f"{result_qkd['total_handshake_ms']:.4f}", "ms")
    print_metric("Network latency", f"{result_qkd['network_latency_ms']:.4f}", "ms")
    print_metric("Compute latency", f"{result_qkd['compute_latency_ms']:.4f}", "ms")
    print_metric("PQ crypto overhead", f"{result_qkd['pq_overhead_bytes']}", "bytes")
    print_metric("Total data transferred", f"{result_qkd['data_transferred_bytes']}", "bytes")
    
    print(f"\n  Timing Breakdown:")
    for phase, duration in result_qkd['timing_breakdown'].items():
        print(f"    {phase:25s}: {duration:.4f} ms")
    
    # Data transfer
    transfer = app.simulate_data_transfer("alice-bob", data_size_bytes=10000)
    print(f"\n  Encrypted Data Transfer (10 KB):")
    print_metric("Throughput", f"{transfer['throughput_mbps']:.2f}", "Mbps")
    print_metric("Encryption overhead", f"{transfer['overhead_ratio']:.2%}")
    print_metric("Total latency", f"{transfer['total_latency_ms']:.4f}", "ms")


def demo_4_eve_attack():
    """Demo 4: Eavesdropper Detection"""
    print_header("Demo 4: Eavesdropper Detection")
    
    intercept_rates = [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]
    qbers = []
    detected = []
    
    print(f"  {'Intercept Rate':>15s}  {'QBER':>8s}  {'Secure?':>8s}  {'Eve Detected':>13s}")
    print(f"  {'-'*15}  {'-'*8}  {'-'*8}  {'-'*13}")
    
    for rate in intercept_rates:
        ec = EavesdropperChannel(distance_km=10.0, intercept_rate=rate)
        qber = ec.expected_qber
        is_detected = qber > 0.11
        qbers.append(qber)
        detected.append(is_detected)
        
        status = "✗ INSECURE" if is_detected else "✓ Secure"
        eve_status = "✓ DETECTED" if is_detected else "Not detected"
        
        print(f"  {rate:>14.0%}  {qber:>8.4f}  {status:>8s}  {eve_status:>13s}")
    
    # Generate plot if matplotlib available
    if HAS_MATPLOTLIB:
        plot_eve_detection(
            intercept_rates, qbers, detected,
            output_path="simulation_results/eve_detection.png"
        )
        print(f"\n  Plot saved: simulation_results/eve_detection.png")


def demo_5_distance_sweep():
    """Demo 5: Key Rate vs Distance Analysis"""
    print_header("Demo 5: Key Rate vs Distance")
    
    scenario = get_scenario("distance_sweep")
    metrics = MetricsCollector("distance_sweep")
    
    distances = []
    key_rates = []
    qbers = []
    
    print(f"  {'Distance':>10s}  {'Key Rate':>14s}  {'QBER':>8s}  {'Max Distance?':>14s}")
    print(f"  {'-'*10}  {'-'*14}  {'-'*8}  {'-'*14}")
    
    for entry in scenario['topologies']:
        dist = entry['distance_km']
        topo = entry['topology']
        
        link_key = list(topo.links.keys())[0]
        qc = topo.links[link_key].quantum_channel
        
        kr = qc.key_rate_per_pulse
        qber = qc.expected_qber
        
        distances.append(dist)
        key_rates.append(kr)
        qbers.append(qber)
        
        metrics.record("distance_km", dist)
        metrics.record("key_rate", kr, distance_km=dist)
        metrics.record("qber", qber, distance_km=dist)
        
        limit = "← near limit" if kr < 1e-6 else ""
        print(f"  {dist:>8.0f} km  {kr:>14.8f}  {qber:>8.4f}  {limit}")
    
    # Generate plots
    if HAS_MATPLOTLIB:
        os.makedirs("simulation_results", exist_ok=True)
        plot_key_rate_vs_distance(
            distances, key_rates,
            output_path="simulation_results/key_rate_vs_distance.png"
        )
        plot_qber_vs_distance(
            distances, qbers,
            output_path="simulation_results/qber_vs_distance.png"
        )
        print(f"\n  Plots saved to simulation_results/")
    
    # Export metrics
    os.makedirs("simulation_results", exist_ok=True)
    metrics.to_csv("simulation_results/distance_sweep.csv")
    metrics.to_json("simulation_results/distance_sweep.json")
    print(f"  Metrics exported to simulation_results/")


def demo_6_scenarios():
    """Demo 6: Available Simulation Scenarios"""
    print_header("Demo 6: Available Scenarios")
    
    scenarios = list_scenarios()
    for i, s in enumerate(scenarios, 1):
        print(f"  {i}. {s['name']:20s} — {s['description']}")


def main():
    print("\n" + "╔" + "═"*58 + "╗")
    print("║" + "  DI-QKD + TLS + NS-3 Network Simulation Demo".center(58) + "║")
    print("║" + "  Quantum-Secured Communication Stack".center(58) + "║")
    print("╚" + "═"*58 + "╝")
    
    start = time.time()
    
    demo_1_channel_models()
    demo_2_qkd_over_fiber()
    demo_3_tls_handshake()
    demo_4_eve_attack()
    demo_5_distance_sweep()
    demo_6_scenarios()
    
    elapsed = time.time() - start
    
    print_header("Summary")
    print(f"  All demos completed in {elapsed:.2f} seconds")
    print(f"  Results directory: simulation_results/")
    if HAS_MATPLOTLIB:
        print(f"  Plots generated: ✓")
    else:
        print(f"  Plots: install matplotlib for visualization")
    print()


if __name__ == '__main__':
    main()
