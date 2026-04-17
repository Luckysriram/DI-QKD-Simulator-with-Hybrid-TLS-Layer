"""
BB84 Quantum Key Distribution Protocol Implementation
Bennett-Brassard 1984
"""

import secrets
from typing import List, Tuple, Dict
from dataclasses import dataclass


@dataclass
class BB84State:
    """Represents a single BB84 quantum state"""
    bit: int  # 0 or 1
    basis: str  # 'z' (rectilinear) or 'x' (diagonal)
    
    def __str__(self):
        state_names = {
            ('0', 'z'): '|0⟩',
            ('1', 'z'): '|1⟩',
            ('0', 'x'): '|+⟩',
            ('1', 'x'): '|-⟩'
        }
        return state_names.get((str(self.bit), self.basis), '?')


class BB84:
    """
    BB84 Quantum Key Distribution Protocol
    
    Protocol steps:
    1. Alice prepares random bits in random bases
    2. Alice sends quantum states to Bob
    3. Bob measures in random bases
    4. Alice and Bob publicly compare bases (not the bits)
    5. Keep only bits where bases match
    """
    
    def __init__(self, key_size: int = 512):
        """Initialize BB84 protocol"""
        self.key_size = key_size
        self.alice_bits = []
        self.alice_bases = []
        self.alice_states = []
        
        self.bob_bases = []
        self.bob_measurements = []
        
        self.shared_bases = []
        self.sifted_key = []
        
    def alice_prepare_states(self) -> List[BB84State]:
        """
        Alice prepares quantum states with random bits and bases
        Returns list of BB84State objects
        """
        self.alice_bits = [secrets.randbelow(2) for _ in range(self.key_size)]
        self.alice_bases = [secrets.choice(['z', 'x']) for _ in range(self.key_size)]
        
        self.alice_states = [
            BB84State(bit=self.alice_bits[i], basis=self.alice_bases[i])
            for i in range(self.key_size)
        ]
        
        return self.alice_states
    
    def bob_measure_states(self) -> List[int]:
        """
        Bob measures received quantum states in random bases
        Returns measurement results
        """
        self.bob_bases = [secrets.choice(['z', 'x']) for _ in range(self.key_size)]
        
        # Bob's measurement: if basis matches Alice's, result is correct;
        # if basis doesn't match, result is random
        self.bob_measurements = []
        for i in range(self.key_size):
            if self.bob_bases[i] == self.alice_bases[i]:
                # Correct basis -> correct result
                self.bob_measurements.append(self.alice_bits[i])
            else:
                # Wrong basis -> random result
                self.bob_measurements.append(secrets.randbelow(2))
        
        return self.bob_measurements
    
    def sift_keys(self) -> List[int]:
        """
        Alice and Bob publicly compare bases and keep only matching ones
        This is the sifted key
        """
        self.shared_bases = []
        self.sifted_key = []
        
        for i in range(self.key_size):
            if self.alice_bases[i] == self.bob_bases[i]:
                self.shared_bases.append(i)
                self.sifted_key.append(self.alice_bits[i])
        
        return self.sifted_key
    
    def error_correction(self, test_size: int = 32) -> Tuple[List[int], float, List[int]]:
        """
        Perform error correction using subset of sifted key
        Returns final key, QBER (Quantum Bit Error Rate), and test positions
        """
        if len(self.sifted_key) < test_size * 2:
            return self.sifted_key, 0.0, []
        
        # Randomly select test positions
        test_positions = sorted(secrets.SystemRandom().sample(
            range(len(self.sifted_key)), min(test_size, len(self.sifted_key) // 2)
        ))
        
        # Check errors in test positions
        errors = 0
        for pos in test_positions:
            sifted_index = self.shared_bases[pos] if pos < len(self.shared_bases) else pos
            bob_bit = self.bob_measurements[sifted_index]
            alice_bit = self.alice_bits[sifted_index]
            if bob_bit != alice_bit:
                errors += 1
        
        # Calculate QBER
        qber = errors / len(test_positions) if test_positions else 0.0
        
        # Remove test positions from final key
        final_key = [
            self.sifted_key[i] 
            for i in range(len(self.sifted_key)) 
            if i not in test_positions
        ]
        
        return final_key, qber, test_positions
    
    def privacy_amplification(self, key: List[int], chunk_size: int = 2) -> List[int]:
        """
        Apply privacy amplification using XOR operations
        This reduces Eve's information while preserving Alice-Bob agreement
        """
        amplified = []
        for i in range(0, len(key) - chunk_size + 1, chunk_size):
            chunk = key[i:i + chunk_size]
            xor_result = 0
            for bit in chunk:
                xor_result ^= bit
            amplified.append(xor_result)
        
        return amplified
    
    def get_statistics(self) -> Dict:
        """Get BB84 protocol statistics"""
        return {
            'total_bits_sent': self.key_size,
            'sifted_key_length': len(self.sifted_key),
            'sift_ratio': len(self.sifted_key) / self.key_size if self.key_size > 0 else 0,
            'bases_matched': len(self.shared_bases),
            'measurement_bases_used': len(set(self.bob_bases)),
        }
    
    def simulate_eve_eavesdropping(self, eve_basis_selection: List[str] = None) -> Dict:
        """
        Simulate Eve's eavesdropping attempt
        Eve measures states in random bases and sends her measurements to Bob
        
        Returns Eve's success stats and detection metrics
        """
        if eve_basis_selection is None:
            eve_basis_selection = [secrets.choice(['z', 'x']) for _ in range(self.key_size)]
        
        eve_measurements = []
        eve_errors = 0
        
        for i in range(self.key_size):
            if eve_basis_selection[i] == self.alice_bases[i]:
                eve_measurements.append(self.alice_bits[i])
            else:
                eve_measurements.append(secrets.randbelow(2))
            
            # Check if Eve causes detectable error
            if eve_basis_selection[i] != self.alice_bases[i]:
                # Eve's wrong basis measurement causes ~50% error rate downstream
                eve_errors += 1
        
        # Check against QBER threshold (typically 11% for BB84)
        QBER_THRESHOLD = 0.11
        
        return {
            'eve_detected': len(self.sifted_key) > 0 and eve_errors / self.key_size > 0.05,
            'eve_error_rate': eve_errors / self.key_size,
            'eve_measurements': eve_measurements,
            'eve_bases': eve_basis_selection
        }
    
    def reset(self):
        """Reset protocol state for new execution"""
        self.alice_bits = []
        self.alice_bases = []
        self.alice_states = []
        self.bob_bases = []
        self.bob_measurements = []
        self.shared_bases = []
        self.sifted_key = []
