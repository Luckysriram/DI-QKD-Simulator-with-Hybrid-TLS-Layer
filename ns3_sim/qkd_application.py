"""
QKD Application — Runs BB84 + CHSH protocols over simulated network channels

This NS-3-style application layer simulates the full QKD protocol stack
operating over the quantum and classical channels from the topology.
"""

import sys
import os
import time
import random
from typing import Dict, Any, Optional, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.bb84 import BB84
from backend.chsh import CHSHBellTest
from backend.quantum_simulator import QuantumSimulator
from ns3_sim.channel_model import QuantumChannel, ClassicalChannel
from ns3_sim.topology import QKDTopology


class QKDApplication:
    """
    Simulates QKD protocol execution over a network topology.
    
    Applies channel effects (loss, noise, latency) to the quantum
    key distribution process, providing realistic performance metrics.
    """
    
    def __init__(self, topology: QKDTopology):
        """
        Args:
            topology: Network topology to run QKD over
        """
        self.topology = topology
        self.results: Dict[str, Any] = {}
        self.execution_log: List[str] = []
    
    def run_bb84_over_channel(
        self,
        link_name: str,
        key_size: int = 512,
    ) -> Dict[str, Any]:
        """
        Run BB84 protocol over a specific network link, applying
        channel effects to the quantum transmission.
        
        Args:
            link_name: Key of the link in topology (e.g., "alice-bob")
            key_size: Number of qubits to send
        
        Returns:
            Protocol results with channel metrics
        """
        start_time = time.time()
        
        # Get the link
        links = self.topology.links
        if link_name not in links:
            # Try reverse
            parts = link_name.split('-')
            if len(parts) == 2:
                reverse = f"{parts[1]}-{parts[0]}"
                if reverse in links:
                    link_name = reverse
        
        link = links[link_name]
        qc = link.quantum_channel
        cc = link.classical_channel
        
        self._log(f"Starting BB84 over link '{link_name}' ({qc.distance_km} km)")
        self._log(f"Channel: loss={qc._total_loss_db:.1f}dB, "
                   f"expected QBER={qc.expected_qber:.4f}")
        
        # Phase 1: Quantum transmission — Alice sends photons to Bob
        self._log(f"Phase 1: Alice sending {key_size} photons...")
        
        qc.reset_metrics()
        
        # Run BB84 protocol
        bb84 = BB84(key_size=key_size)
        alice_states = bb84.alice_prepare_states()
        
        # Simulate each photon going through the quantum channel
        detected_indices = []
        channel_errors = []
        
        for i in range(key_size):
            detected, error, latency = qc.transmit_photon()
            if detected:
                detected_indices.append(i)
                channel_errors.append(error)
        
        self._log(f"  Photons detected: {len(detected_indices)}/{key_size} "
                   f"({len(detected_indices)/key_size:.1%})")
        
        # Bob measures only detected photons
        bob_measurements = bb84.bob_measure_states()
        
        # Apply channel errors to Bob's measurements
        for idx, (det_idx, error) in enumerate(zip(detected_indices, channel_errors)):
            if error and det_idx < len(bb84.bob_measurements):
                # Flip Bob's bit due to channel error
                bb84.bob_measurements[det_idx] = 1 - bb84.bob_measurements[det_idx]
        
        # Phase 2: Classical channel — basis comparison
        self._log("Phase 2: Basis comparison over classical channel...")
        
        # Simulate classical message exchange
        basis_msg_size = key_size // 4  # Compressed basis info
        delivered, classical_latency = cc.transmit_reliable(basis_msg_size)
        
        if not delivered:
            self._log("ERROR: Classical channel failed!")
            return {'status': 'failed', 'reason': 'classical_channel_failure'}
        
        self._log(f"  Classical latency: {classical_latency:.2f} ms")
        
        # Phase 3: Key sifting
        sifted_key = bb84.sift_keys()
        self._log(f"Phase 3: Sifted key: {len(sifted_key)} bits")
        
        # Phase 4: Error correction
        final_key, qber, test_positions = bb84.error_correction(test_size=32)
        
        # Adjust QBER to account for channel errors
        channel_qber = qc.expected_qber
        effective_qber = min(qber + channel_qber, 0.5)
        
        self._log(f"Phase 4: QBER = {effective_qber:.4f} "
                   f"(protocol={qber:.4f}, channel={channel_qber:.4f})")
        
        # Phase 5: Privacy amplification
        amplified_key = bb84.privacy_amplification(final_key, chunk_size=2)
        self._log(f"Phase 5: Final key: {len(amplified_key)} bits")
        
        elapsed = time.time() - start_time
        
        result = {
            'status': 'success',
            'link': link_name,
            'distance_km': qc.distance_km,
            'key_size_requested': key_size,
            'photons_detected': len(detected_indices),
            'detection_rate': len(detected_indices) / max(key_size, 1),
            'sifted_key_length': len(sifted_key),
            'final_key_length': len(amplified_key),
            'effective_qber': round(effective_qber, 6),
            'channel_qber': round(channel_qber, 6),
            'protocol_qber': round(qber, 6),
            'is_secure': effective_qber < 0.11,
            'key_rate_per_pulse': round(qc.key_rate_per_pulse, 8),
            'classical_latency_ms': round(classical_latency, 4),
            'total_time_s': round(elapsed, 4),
            'channel_metrics': qc.metrics.to_dict(),
            'final_key': amplified_key,
        }
        
        self.results['bb84'] = result
        return result
    
    def run_chsh_over_channel(
        self,
        link_name: str,
        num_rounds: int = 1000,
        state_type: str = 'entangled'
    ) -> Dict[str, Any]:
        """
        Run CHSH Bell test over a network link.
        
        The quantum channel affects the Bell violation measurement
        by introducing noise that reduces correlations.
        """
        start_time = time.time()
        
        link = self.topology.links[link_name]
        qc = link.quantum_channel
        
        self._log(f"Starting CHSH Bell test over '{link_name}' "
                   f"({num_rounds} rounds, {state_type})")
        
        # Create quantum state
        quantum_sim = QuantumSimulator()
        if state_type == 'entangled':
            state = quantum_sim.create_bell_pair('phi_plus')
        else:
            state = quantum_sim.create_separable_pair()
        
        # Run CHSH
        chsh = CHSHBellTest(num_rounds=num_rounds)
        measurements = chsh.run_bell_test(state)
        
        # Apply channel depolarization to measurements
        # Channel noise reduces Bell violation
        depolar_factor = 1.0 - qc._depolar_prob
        
        chsh_stats = chsh.get_statistics()
        raw_chsh_value = chsh_stats['chsh_value']
        
        # Effective CHSH value after channel noise
        # Depolarization reduces S by a factor of (1 - depolar_prob)
        effective_chsh = raw_chsh_value * depolar_factor
        
        di_cert = chsh.device_independent_certification()
        
        elapsed = time.time() - start_time
        
        result = {
            'status': 'success',
            'link': link_name,
            'distance_km': qc.distance_km,
            'num_rounds': num_rounds,
            'raw_chsh_value': round(raw_chsh_value, 6),
            'effective_chsh_value': round(effective_chsh, 6),
            'depolarization_factor': round(depolar_factor, 6),
            'violates_bell': effective_chsh > 2.0,
            'device_independent': di_cert['device_independent'] and effective_chsh > 2.0,
            'security_robustness': di_cert['security_robustness'],
            'certified_key_rate': round(di_cert['certified_key_rate'], 6),
            'total_time_s': round(elapsed, 4),
        }
        
        self.results['chsh'] = result
        return result
    
    def run_full_qkd(
        self,
        link_name: str,
        key_size: int = 512,
        chsh_rounds: int = 1000
    ) -> Dict[str, Any]:
        """
        Run the full DI-QKD protocol (BB84 + CHSH) over a network link.
        """
        self._log("=" * 50)
        self._log("Starting Full DI-QKD over Network")
        self._log("=" * 50)
        
        bb84_result = self.run_bb84_over_channel(link_name, key_size)
        chsh_result = self.run_chsh_over_channel(link_name, chsh_rounds)
        
        # Security assessment
        is_secure = (
            bb84_result.get('is_secure', False) and
            chsh_result.get('violates_bell', False)
        )
        
        security_level = 'Low'
        if is_secure and chsh_result.get('device_independent'):
            security_level = 'Very High (Device-Independent)'
        elif is_secure:
            security_level = 'High'
        elif bb84_result.get('is_secure'):
            security_level = 'Medium'
        
        combined = {
            'bb84': bb84_result,
            'chsh': chsh_result,
            'security_level': security_level,
            'is_secure': is_secure,
            'execution_log': list(self.execution_log),
        }
        
        self.results['full_qkd'] = combined
        self._log(f"Security Level: {security_level}")
        self._log("=" * 50)
        
        return combined
    
    def _log(self, message: str):
        """Log simulation message."""
        self.execution_log.append(message)
