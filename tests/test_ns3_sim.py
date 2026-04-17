"""
Test Suite for NS-3 Network Simulation

Tests channel models, topology, scenarios, and metrics collection.
"""

import sys
import os
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ns3_sim.channel_model import (
    QuantumChannel, ClassicalChannel, EavesdropperChannel, ChannelMetrics
)
from ns3_sim.topology import QKDTopology, NetworkNode, NodeType
from ns3_sim.scenarios import get_scenario, list_scenarios
from ns3_sim.metrics import MetricsCollector
from ns3_sim.qkd_application import QKDApplication
from ns3_sim.tls_application import TLSApplication


class TestQuantumChannel:
    """Tests for quantum channel model."""
    
    def test_creation(self):
        qc = QuantumChannel(distance_km=10.0)
        assert qc.distance_km == 10.0
        assert qc.attenuation == 0.2
    
    def test_transmission_probability_decreases_with_distance(self):
        short = QuantumChannel(distance_km=1.0)
        long = QuantumChannel(distance_km=100.0)
        assert short.transmission_probability > long.transmission_probability
    
    def test_expected_qber_increases_with_distance(self):
        short = QuantumChannel(distance_km=1.0)
        long = QuantumChannel(distance_km=100.0)
        assert short.expected_qber < long.expected_qber
    
    def test_key_rate_decreases_with_distance(self):
        short = QuantumChannel(distance_km=1.0)
        long = QuantumChannel(distance_km=50.0)
        assert short.key_rate_per_pulse > long.key_rate_per_pulse
    
    def test_photon_transmission(self):
        qc = QuantumChannel(distance_km=1.0)  # Short distance, high detection
        results = qc.transmit_batch(1000)
        
        assert results['sent'] == 1000
        assert results['detected'] > 0
        assert results['detected'] <= 1000
        assert 0 <= results['qber'] <= 1
    
    def test_long_distance_high_loss(self):
        qc = QuantumChannel(distance_km=200.0)
        results = qc.transmit_batch(100)
        assert results['detection_rate'] < 0.01  # Very low at 200km
    
    def test_metrics_reset(self):
        qc = QuantumChannel(distance_km=10.0)
        qc.transmit_batch(100)
        assert qc.metrics.total_sent > 0
        
        qc.reset_metrics()
        assert qc.metrics.total_sent == 0
    
    def test_get_info(self):
        qc = QuantumChannel(distance_km=10.0)
        info = qc.get_info()
        assert info['type'] == 'quantum'
        assert info['distance_km'] == 10.0
        assert 'transmission_probability' in info
        assert 'expected_qber' in info


class TestClassicalChannel:
    """Tests for classical channel model."""
    
    def test_creation(self):
        cc = ClassicalChannel(distance_km=10.0, bandwidth_mbps=1000)
        assert cc.distance_km == 10.0
        assert cc.bandwidth_mbps == 1000
    
    def test_transmission(self):
        cc = ClassicalChannel(distance_km=10.0, packet_loss_rate=0.0)
        delivered, latency = cc.transmit(1000)
        assert delivered is True
        assert latency > 0
    
    def test_packet_loss(self):
        cc = ClassicalChannel(distance_km=10.0, packet_loss_rate=1.0)
        delivered, _ = cc.transmit(1000)
        assert delivered is False
    
    def test_reliable_transmission_retries(self):
        cc = ClassicalChannel(distance_km=10.0, packet_loss_rate=0.5)
        delivered, latency = cc.transmit_reliable(1000, max_retries=10)
        # With 50% loss and 10 retries, should usually succeed
        # (probability of all failing = 0.5^11 ≈ 0.05%)
    
    def test_latency_increases_with_distance(self):
        short = ClassicalChannel(distance_km=1.0, jitter_ms=0)
        long = ClassicalChannel(distance_km=100.0, jitter_ms=0)
        
        _, lat_short = short.transmit(100)
        _, lat_long = long.transmit(100)
        
        assert lat_long > lat_short


class TestEavesdropperChannel:
    """Tests for eavesdropper channel."""
    
    def test_creation(self):
        ec = EavesdropperChannel(distance_km=20.0, intercept_rate=0.5)
        assert ec.intercept_rate == 0.5
        assert ec.eve_position_km == 5.0  # Default: distance/2
    
    def test_higher_qber_with_eve(self):
        normal = QuantumChannel(distance_km=10.0)
        with_eve = EavesdropperChannel(distance_km=10.0, intercept_rate=0.5)
        
        # Eve should increase QBER
        assert with_eve.expected_qber > normal.expected_qber
    
    def test_full_intercept_exceeds_threshold(self):
        ec = EavesdropperChannel(distance_km=10.0, intercept_rate=1.0)
        # Full intercept should push QBER above 11% threshold
        assert ec.expected_qber > 0.11
    
    def test_eve_metrics(self):
        ec = EavesdropperChannel(distance_km=5.0, intercept_rate=0.5)
        ec.transmit_batch(1000)
        
        info = ec.get_info()
        assert info['type'] == 'eavesdropper'
        assert info['eve_metrics']['intercepted'] > 0


class TestTopology:
    """Tests for QKD network topology."""
    
    def test_point_to_point(self):
        topo = QKDTopology.create_point_to_point(distance_km=10.0)
        assert len(topo.nodes) == 2
        assert len(topo.links) == 1
        assert 'alice' in topo.nodes
        assert 'bob' in topo.nodes
    
    def test_with_eve(self):
        topo = QKDTopology.create_with_eve(distance_km=20.0, intercept_rate=0.5)
        assert len(topo.nodes) == 3
        assert 'eve' in topo.nodes
    
    def test_star_topology(self):
        topo = QKDTopology.create_star(num_users=4)
        assert len(topo.nodes) == 5  # KMS + 4 users
        assert len(topo.links) == 4
    
    def test_metro_ring(self):
        topo = QKDTopology.create_metro_ring(num_nodes=4, ring_circumference_km=40.0)
        assert len(topo.nodes) == 4
        assert len(topo.links) == 4  # Ring has N links
    
    def test_topology_info(self):
        topo = QKDTopology.create_point_to_point(10.0)
        info = topo.get_topology_info()
        assert info['num_nodes'] == 2
        assert info['num_links'] == 1
    
    def test_add_custom_node_and_link(self):
        topo = QKDTopology(name="custom")
        topo.add_node("a", NodeType.ALICE, 0)
        topo.add_node("b", NodeType.BOB, 50)
        topo.add_link("a", "b", distance_km=50)
        
        link = topo.get_link("a", "b")
        assert link.quantum_channel.distance_km == 50
        assert link.classical_channel.distance_km == 50


class TestScenarios:
    """Tests for pre-built scenarios."""
    
    def test_list_scenarios(self):
        scenarios = list_scenarios()
        assert len(scenarios) >= 5
        names = [s['name'] for s in scenarios]
        assert 'fiber_10km' in names
        assert 'eve_attack' in names
    
    def test_fiber_10km(self):
        config = get_scenario('fiber_10km')
        assert 'topology' in config
        assert config['topology'].name == 'fiber_10km'
    
    def test_fiber_100km(self):
        config = get_scenario('fiber_100km')
        assert config['topology'].name == 'fiber_100km'
    
    def test_satellite_leo(self):
        config = get_scenario('satellite_leo')
        nodes = config['topology'].nodes
        assert 'ground_alice' in nodes
        assert 'satellite' in nodes
    
    def test_distance_sweep(self):
        config = get_scenario('distance_sweep')
        assert 'topologies' in config
        assert len(config['topologies']) >= 10
    
    def test_unknown_scenario_raises(self):
        with pytest.raises(ValueError):
            get_scenario('nonexistent')


class TestMetrics:
    """Tests for metrics collection."""
    
    def test_record_and_get(self):
        mc = MetricsCollector("test")
        mc.record("key_rate", 0.001, distance_km=10)
        mc.record("key_rate", 0.0005, distance_km=20)
        
        values = mc.get_metric_values("key_rate")
        assert len(values) == 2
        assert values[0] == 0.001
    
    def test_summary(self):
        mc = MetricsCollector("test")
        mc.record("qber", 0.03)
        mc.record("qber", 0.05)
        mc.record("qber", 0.07)
        
        summary = mc.summary()
        assert summary['metrics']['qber']['count'] == 3
        assert summary['metrics']['qber']['min'] == 0.03
        assert summary['metrics']['qber']['max'] == 0.07
    
    def test_csv_export(self):
        mc = MetricsCollector("test")
        mc.record("key_rate", 0.001, distance_km=10)
        mc.record("key_rate", 0.0005, distance_km=20)
        
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            mc.to_csv(f.name)
            
            # Read back
            with open(f.name, 'r') as f2:
                content = f2.read()
                assert 'key_rate' in content
                assert '0.001' in content
        
        os.unlink(f.name)
    
    def test_json_export(self):
        mc = MetricsCollector("test")
        mc.record("qber", 0.05)
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            mc.to_json(f.name)
            
            import json
            with open(f.name, 'r') as f2:
                data = json.load(f2)
                assert data['scenario'] == 'test'
        
        os.unlink(f.name)


class TestQKDApplication:
    """Tests for QKD application over simulated network."""
    
    def test_bb84_over_short_fiber(self):
        topo = QKDTopology.create_point_to_point(distance_km=5.0)
        app = QKDApplication(topo)
        
        result = app.run_bb84_over_channel("alice-bob", key_size=256)
        assert result['status'] == 'success'
        assert result['distance_km'] == 5.0
        assert result['photons_detected'] > 0
        assert 'effective_qber' in result
    
    def test_bb84_security_check(self):
        topo = QKDTopology.create_point_to_point(distance_km=5.0)
        app = QKDApplication(topo)
        
        result = app.run_bb84_over_channel("alice-bob", key_size=256)
        # Short distance should be secure
        assert result['is_secure'] is True
    
    def test_chsh_over_channel(self):
        topo = QKDTopology.create_point_to_point(distance_km=5.0)
        app = QKDApplication(topo)
        
        result = app.run_chsh_over_channel("alice-bob", num_rounds=500)
        assert result['status'] == 'success'
        assert 'effective_chsh_value' in result


class TestTLSApplication:
    """Tests for TLS application over simulated network."""
    
    def test_handshake_simulation(self):
        topo = QKDTopology.create_point_to_point(distance_km=10.0)
        app = TLSApplication(topo)
        
        result = app.simulate_handshake("alice-bob")
        assert 'total_handshake_ms' in result
        assert result['total_handshake_ms'] > 0
        assert 'timing_breakdown' in result
    
    def test_data_transfer_simulation(self):
        topo = QKDTopology.create_point_to_point(distance_km=10.0)
        app = TLSApplication(topo)
        
        result = app.simulate_data_transfer("alice-bob", data_size_bytes=10000)
        assert result['data_size_bytes'] == 10000
        assert result['throughput_mbps'] > 0
    
    def test_full_session(self):
        topo = QKDTopology.create_point_to_point(distance_km=10.0)
        app = TLSApplication(topo)
        
        result = app.simulate_full_session("alice-bob")
        assert 'handshake' in result
        assert 'data_transfer' in result
        assert result['total_session_ms'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
