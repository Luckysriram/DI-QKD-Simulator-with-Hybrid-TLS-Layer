"""
Device-Independent Quantum Key Distribution (DI-QKD) Simulator
Integrates BB84 protocol with CHSH Bell test for device-independent security
"""

from backend.bb84 import BB84
from backend.chsh import CHSHBellTest
from backend.quantum_simulator import QuantumSimulator, QuantumState
from typing import Dict, List, Tuple
import json
from datetime import datetime


class DIQKDSimulator:
    """
    Main DI-QKD Simulator combining:
    - BB84 for practical key distribution
    - CHSH for device-independent security certification
    - Quantum state simulation for realistic scenarios
    """
    
    def __init__(self, key_size: int = 512, num_chsh_rounds: int = 1000):
        """Initialize DI-QKD simulator"""
        self.key_size = key_size
        self.num_chsh_rounds = num_chsh_rounds
        
        # Protocol instances
        self.bb84 = BB84(key_size=key_size)
        self.chsh = CHSHBellTest(num_rounds=num_chsh_rounds)
        self.quantum_sim = QuantumSimulator()
        
        # Results storage
        self.results = {
            'timestamp': None,
            'bb84_results': None,
            'chsh_results': None,
            'combined_key': None,
            'security_certification': None,
            'simulation_params': None,
        }
        
        self.execution_log = []
    
    def run_bb84_protocol(self, use_quantum_sim: bool = True) -> Dict:
        """
        Execute BB84 protocol
        
        Steps:
        1. Alice prepares quantum states with random bits in random bases
        2. Bob measures in random bases
        3. Sift keys by comparing bases
        4. Error correction
        5. Privacy amplification
        """
        self.log("Starting BB84 protocol execution")
        
        # Step 1: Alice prepares states
        alice_states = self.bb84.alice_prepare_states()
        self.log(f"Alice prepared {self.key_size} quantum states")
        
        # Step 2: Bob measures states
        bob_measurements = self.bb84.bob_measure_states()
        self.log("Bob measured quantum states")
        
        # Step 3: Sift keys
        sifted_key = self.bb84.sift_keys()
        self.log(f"Sifted key length: {len(sifted_key)} bits (efficiency: {len(sifted_key)/self.key_size:.2%})")
        
        # Step 4: Error correction
        final_key, qber, test_positions = self.bb84.error_correction(test_size=32)
        self.log(f"QBER (Quantum Bit Error Rate): {qber:.4f}")
        
        # Step 5: Privacy amplification
        amplified_key = self.bb84.privacy_amplification(final_key, chunk_size=2)
        self.log(f"Final key length after privacy amplification: {len(amplified_key)} bits")
        
        # Simulate Eve eavesdropping
        eve_stats = self.bb84.simulate_eve_eavesdropping()
        eve_detected = eve_stats['eve_detected']
        self.log(f"Eve eavesdropping simulation - Detected: {eve_detected}")
        
        bb84_results = {
            'initial_bits': self.key_size,
            'sifted_key_length': len(sifted_key),
            'final_key_length': len(amplified_key),
            'qber': qber,
            'eve_detected': eve_detected,
            'eve_error_rate': eve_stats['eve_error_rate'],
            'statistics': self.bb84.get_statistics(),
            'final_key': amplified_key,
            'sifted_key': sifted_key,
        }
        
        self.results['bb84_results'] = bb84_results
        return bb84_results
    
    def run_chsh_bell_test(self, state_type: str = 'entangled') -> Dict:
        """
        Execute CHSH Bell test for device-independent certification
        
        state_type: 'entangled' for Bell states, 'separable' for product states
        """
        self.log(f"Starting CHSH Bell test with {state_type} state")
        
        # Prepare quantum state
        if state_type == 'entangled':
            entangled_state = self.quantum_sim.create_bell_pair('phi_plus')
            self.log("Created maximally entangled Bell state |Φ+⟩")
        else:
            entangled_state = self.quantum_sim.create_separable_pair()
            self.log("Created separable product state")
        
        # Run Bell test
        measurements = self.chsh.run_bell_test(entangled_state)
        self.log(f"Completed {self.num_chsh_rounds} CHSH measurements")
        
        # Calculate statistics
        chsh_stats = self.chsh.get_statistics()
        self.log(f"CHSH value: {chsh_stats['chsh_value']:.4f}")
        self.log(f"Bell violation: {chsh_stats['violates_bell']}")
        
        # Device-independent certification
        di_cert = self.chsh.device_independent_certification()
        self.log(f"Device-independent certified: {di_cert['device_independent']}")
        
        chsh_results = {
            'chsh_value': chsh_stats['chsh_value'],
            'violates_bell': chsh_stats['violates_bell'],
            'violation_margin': chsh_stats['violation_margin'],
            'quantum_advantage': chsh_stats['quantum_advantage'],
            'correlations': chsh_stats['correlations'],
            'device_independent': di_cert['device_independent'],
            'security_robustness': di_cert['security_robustness'],
            'certified_key_rate': di_cert['certified_key_rate'],
            'min_entropy': di_cert['min_entropy'],
            'statistics': chsh_stats,
        }
        
        self.results['chsh_results'] = chsh_results
        return chsh_results
    
    def combine_keys(self) -> List[int]:
        """
        Combine BB84 and CHSH keys for enhanced security
        Uses XOR to mix keys if both are available
        """
        if not self.results['bb84_results'] or not self.results['chsh_results']:
            self.log("Warning: One or both protocols not executed yet")
            return []
        
        bb84_key = self.results['bb84_results'].get('final_key', [])
        
        # Extract CHSH key
        chsh_key = self.chsh.extract_key_from_chsh((0, 0))
        
        # Combine keys via XOR (symmetric combination)
        min_length = min(len(bb84_key), len(chsh_key))
        if min_length == 0:
            combined_key = []
        else:
            combined_key = [
                bb84_key[i] ^ chsh_key[i] for i in range(min_length)
            ]
        
        self.log(f"Combined key from BB84 and CHSH: {len(combined_key)} bits")
        self.results['combined_key'] = combined_key
        return combined_key
    
    def run_full_simulation(self, chsh_state: str = 'entangled') -> Dict:
        """
        Run complete DI-QKD simulation:
        1. BB84 protocol execution
        2. CHSH Bell test
        3. Device-independent certification
        4. Key combination
        """
        self.log("=" * 60)
        self.log("Starting Full DI-QKD Simulation")
        self.log("=" * 60)
        self.results['timestamp'] = datetime.now().isoformat()
        self.results['simulation_params'] = {
            'key_size': self.key_size,
            'chsh_rounds': self.num_chsh_rounds,
            'chsh_state_type': chsh_state,
        }
        
        # Execute protocols
        bb84_results = self.run_bb84_protocol()
        chsh_results = self.run_chsh_bell_test(state_type=chsh_state)
        combined_key = self.combine_keys()
        
        # Security assessment
        security_cert = self.assess_security(bb84_results, chsh_results)
        self.results['security_certification'] = security_cert
        
        self.log("=" * 60)
        self.log("DI-QKD Simulation Completed")
        self.log("=" * 60)
        
        return self.results
    
    def assess_security(self, bb84_results: Dict, chsh_results: Dict) -> Dict:
        """
        Comprehensive security assessment
        Combines classical and quantum security metrics
        """
        # BB84 security metrics
        bb84_secure = bb84_results['qber'] < 0.11  # Standard QBER threshold
        eve_detected = bb84_results['eve_detected']
        
        # CHSH security metrics
        di_certified = chsh_results['device_independent']
        robustness = chsh_results['security_robustness']
        
        # Overall assessment
        security_level = 'Low'
        if di_certified and bb84_secure:
            if robustness == 'Strong':
                security_level = 'Very High (Device-Independent Certified)'
            elif robustness == 'Moderate':
                security_level = 'High'
            else:
                security_level = 'Medium'
        elif bb84_secure:
            security_level = 'Medium-High'
        
        return {
            'overall_security_level': security_level,
            'bb84_secure': bb84_secure,
            'eve_detected': eve_detected,
            'device_independent_certified': di_certified,
            'di_robustness': robustness,
            'quantum_advantage': chsh_results['violates_bell'],
            'key_size': len(self.results.get('combined_key', [])),
            'recommendations': self._get_recommendations(bb84_results, chsh_results),
        }
    
    def _get_recommendations(self, bb84_results: Dict, chsh_results: Dict) -> List[str]:
        """Generate security recommendations"""
        recommendations = []
        
        if bb84_results['qber'] > 0.11:
            recommendations.append("QBER exceeds safe threshold - possible eavesdropping detected")
        
        if not chsh_results['device_independent']:
            recommendations.append("No Bell violation - cannot certify device-independent security")
        
        if len(self.results.get('combined_key', [])) < 256:
            recommendations.append("Generated key is small - consider running with larger parameters")
        
        if chsh_results['security_robustness'] == 'Weak':
            recommendations.append("CHSH robustness is weak - improve entanglement quality")
        
        if not recommendations:
            recommendations.append("All security checks passed - key is secure for use")
        
        return recommendations
    
    def log(self, message: str):
        """Log execution message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.execution_log.append(log_entry)
        print(log_entry)
    
    def export_results(self, filename: str = None) -> str:
        """Export results to JSON file"""
        if filename is None:
            filename = f"diqkd_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Prepare exportable results
        export_data = {
            'timestamp': self.results['timestamp'],
            'simulation_params': self.results['simulation_params'],
            'execution_log': self.execution_log,
            'key_statistics': {
                'input_bits': self.results['bb84_results']['initial_bits'],
                'sifted_key_length': self.results['bb84_results']['sifted_key_length'],
                'final_key_length': self.results['bb84_results']['final_key_length'],
                'combined_key_length': len(self.results.get('combined_key', [])),
            },
            'security_certification': self.results['security_certification'],
            'bb84_statistics': self.results['bb84_results']['statistics'],
            'chsh_correlations': self.results['chsh_results']['correlations'],
        }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        self.log(f"Results exported to {filename}")
        return filename
    
    def reset(self):
        """Reset simulator for new run"""
        self.bb84.reset()
        self.chsh.reset()
        self.results = {
            'timestamp': None,
            'bb84_results': None,
            'chsh_results': None,
            'combined_key': None,
            'security_certification': None,
            'simulation_params': None,
        }
        self.execution_log = []
