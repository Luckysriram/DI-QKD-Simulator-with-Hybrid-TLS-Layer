"""
CHSH (Clauser-Horne-Shimony-Holt) Bell Test Implementation
Used for Device-Independent Quantum Key Distribution
"""

import numpy as np
from typing import Dict, List, Tuple
import secrets
from dataclasses import dataclass


@dataclass
class CHSHMeasurement:
    """Represents a single CHSH measurement round"""
    alice_input: int  # 0 or 1
    bob_input: int    # 0 or 1
    alice_output: int # 0 or 1
    bob_output: int   # 0 or 1
    
    @property
    def xor_result(self) -> int:
        """Returns XOR of alice and bob outputs"""
        return self.alice_output ^ self.bob_output


class CHSHBellTest:
    """
    CHSH Bell Test for Device-Independent QKD
    
    Tests the CHSH inequality: S = |E(0,0) + E(0,1) + E(1,0) - E(1,1)| ≤ 2
    
    Where E(a,b) is the correlation for Alice setting a, Bob setting b
    Quantum violations: up to 2√2 ≈ 2.828
    Classical violations: impossible (S ≤ 2)
    
    For Device-Independent QKD:
    - If S > 2, the system uses quantum entanglement
    - Higher S values indicate stronger entanglement
    - Can be used to certify keys without trusting device internals
    """
    
    def __init__(self, num_rounds: int = 1000):
        """Initialize CHSH Bell test"""
        self.num_rounds = num_rounds
        self.measurements: List[CHSHMeasurement] = []
        self.correlations: Dict = {}
        
    def alice_measure(self, setting: int, entangled_state=None) -> int:
        """
        Alice measures her qubit with setting 0 (Z basis) or 1 (X basis)
        Returns output 0 or 1
        
        For simulated entangled state: can be correlated with Bob
        """
        if entangled_state is not None:
            # Simulate correlated measurement
            basis = 'z' if setting == 0 else 'x'
            alice_output, _ = entangled_state.measure(basis, 'z')
            return alice_output
        else:
            # Random output when no entanglement
            return secrets.randbelow(2)
    
    def bob_measure(self, setting: int, entangled_state=None) -> int:
        """
        Bob measures his qubit with setting 0 (Z basis) or 1 (X basis)
        Returns output 0 or 1
        
        For simulated entangled state: can be correlated with Alice
        """
        if entangled_state is not None:
            # Simulate correlated measurement
            basis = 'z' if setting == 0 else 'x'
            _, bob_output = entangled_state.measure('z', basis)
            return bob_output
        else:
            # Random output when no entanglement
            return secrets.randbelow(2)
    
    def run_bell_test(self, entangled_state=None) -> List[CHSHMeasurement]:
        """
        Run complete CHSH Bell test
        
        Each round:
        1. Alice and Bob randomly select measurement settings (0 or 1)
        2. They measure their qubits
        3. Record the result
        
        Return list of measurements
        """
        self.measurements = []
        
        for _ in range(self.num_rounds):
            # Random measurement settings
            alice_setting = secrets.randbelow(2)
            bob_setting = secrets.randbelow(2)
            
            # Perform measurements
            alice_output = self.alice_measure(alice_setting, entangled_state)
            bob_output = self.bob_measure(bob_setting, entangled_state)
            
            # Record
            measurement = CHSHMeasurement(
                alice_input=alice_setting,
                bob_input=bob_setting,
                alice_output=alice_output,
                bob_output=bob_output
            )
            self.measurements.append(measurement)
        
        return self.measurements
    
    def calculate_chsh_value(self) -> float:
        """
        Calculate CHSH value S from measurements
        
        S = |E(0,0) + E(0,1) + E(1,0) - E(1,1)|
        
        Where E(a,b) is correlation for Alice setting a, Bob setting b
        Correlation = (agreements - disagreements) / total
        """
        if not self.measurements:
            return 0.0
        
        # Calculate correlations for each setting pair
        correlations = {}
        for alice_setting, bob_setting in [(0,0), (0,1), (1,0), (1,1)]:
            relevant = [
                m for m in self.measurements
                if m.alice_input == alice_setting and m.bob_input == bob_setting
            ]
            
            if relevant:
                agreements = sum(1 for m in relevant if m.alice_output == m.bob_output)
                disagreements = len(relevant) - agreements
                correlation = (agreements - disagreements) / len(relevant)
                correlations[f'E({alice_setting},{bob_setting})'] = correlation
            else:
                correlations[f'E({alice_setting},{bob_setting})'] = 0.0
        
        self.correlations = correlations
        
        # CHSH value
        e_00 = correlations['E(0,0)']
        e_01 = correlations['E(0,1)']
        e_10 = correlations['E(1,0)']
        e_11 = correlations['E(1,1)']
        
        s_value = abs(e_00 + e_01 + e_10 - e_11)
        return s_value
    
    def get_statistics(self) -> Dict:
        """Get detailed CHSH statistics"""
        s_value = self.calculate_chsh_value()
        
        # Count setting combinations
        setting_counts = {
            (0,0): sum(1 for m in self.measurements if m.alice_input == 0 and m.bob_input == 0),
            (0,1): sum(1 for m in self.measurements if m.alice_input == 0 and m.bob_input == 1),
            (1,0): sum(1 for m in self.measurements if m.alice_input == 1 and m.bob_input == 0),
            (1,1): sum(1 for m in self.measurements if m.alice_input == 1 and m.bob_input == 1),
        }
        
        # Count agreements for each setting
        agreements = {}
        for a_set, b_set in [(0,0), (0,1), (1,0), (1,1)]:
            relevant = [
                m for m in self.measurements
                if m.alice_input == a_set and m.bob_input == b_set
            ]
            agreements[(a_set, b_set)] = sum(1 for m in relevant if m.xor_result == 0)
        
        return {
            'chsh_value': s_value,
            'violates_bell': s_value > 2.0,
            'violation_margin': s_value - 2.0,
            'quantum_advantage': 2 * np.sqrt(2),  # Maximum quantum value
            'correlations': self.correlations,
            'setting_distribution': setting_counts,
            'agreements': agreements,
            'total_rounds': self.num_rounds,
        }
    
    def extract_key_from_chsh(self, min_setting_pair: Tuple[int, int] = (0, 0)) -> List[int]:
        """
        Extract raw key from CHSH measurements
        Typically use one consistent setting pair to reduce information leakage
        
        Returns list of XOR outputs where Alice and Bob had the specified settings
        """
        key = [
            m.xor_result
            for m in self.measurements
            if (m.alice_input, m.bob_input) == min_setting_pair
        ]
        return key
    
    def device_independent_certification(self) -> Dict:
        """
        Certify device independence based on CHSH violation
        
        Key idea: If CHSH value S > 2, the system must use quantum entanglement
        The amount of violation bounds the device-independent key rate
        
        Returns certification metrics
        """
        s_value = self.calculate_chsh_value()
        
        # Theoretical bounds (simplified)
        # Based on: Robust device-independent QKD with causally independent measurements
        
        if s_value <= 2.0:
            # No Bell violation - no quantum advantage
            certified_key_rate = 0.0
            min_entropy = 0.0
            robustness = 'Failed'
        else:
            # Bell violation detected
            # Approximate key rate from CHSH (simplified)
            violation_ratio = (s_value - 2.0) / (2 * np.sqrt(2) - 2.0)
            certified_key_rate = violation_ratio * 0.5  # Rough approximation
            
            # Min-entropy lower bound (bits per round)
            min_entropy = max(0, np.log2(1 + violation_ratio))
            
            # Robustness assessment
            if s_value > 2.4:
                robustness = 'Strong'
            elif s_value > 2.1:
                robustness = 'Moderate'
            else:
                robustness = 'Weak'
        
        return {
            'chsh_value': s_value,
            'bell_violation': s_value > 2.0,
            'certified_key_rate': certified_key_rate,
            'min_entropy': min_entropy,
            'security_robustness': robustness,
            'quantum_certified': s_value > 2.0,
            'device_independent': s_value > 2.0,
        }
    
    def reset(self):
        """Reset test state for new run"""
        self.measurements = []
        self.correlations = {}
