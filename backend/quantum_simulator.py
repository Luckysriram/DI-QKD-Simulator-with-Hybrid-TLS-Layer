"""
Quantum State Simulator for DI-QKD
Supports entangled state generation and measurement simulation
"""

import numpy as np
from typing import Tuple, List, Dict
import secrets


class QuantumState:
    """Represents a quantum state in 2-qubit system"""
    
    def __init__(self, amplitudes: np.ndarray):
        """
        Initialize quantum state with amplitudes for 4 basis states: |00>, |01>, |10>, |11>
        """
        self.amplitudes = amplitudes / np.linalg.norm(amplitudes)
    
    @staticmethod
    def bell_state(state_type: str = 'phi_plus') -> 'QuantumState':
        """
        Create Bell states (maximally entangled states)
        
        |Φ+⟩ = (1/√2)(|00⟩ + |11⟩)
        |Φ-⟩ = (1/√2)(|00⟩ - |11⟩)
        |Ψ+⟩ = (1/√2)(|01⟩ + |10⟩)
        |Ψ-⟩ = (1/√2)(|01⟩ - |10⟩)
        """
        if state_type == 'phi_plus':
            amplitudes = np.array([1, 0, 0, 1]) / np.sqrt(2)
        elif state_type == 'phi_minus':
            amplitudes = np.array([1, 0, 0, -1]) / np.sqrt(2)
        elif state_type == 'psi_plus':
            amplitudes = np.array([0, 1, 1, 0]) / np.sqrt(2)
        elif state_type == 'psi_minus':
            amplitudes = np.array([0, 1, -1, 0]) / np.sqrt(2)
        else:
            amplitudes = np.array([1, 0, 0, 1]) / np.sqrt(2)
        
        return QuantumState(amplitudes)
    
    @staticmethod
    def product_state(qubit1: str = '0', qubit2: str = '0') -> 'QuantumState':
        """Create separable product states"""
        basis_states = {
            '0': np.array([1, 0]),
            '1': np.array([0, 1]),
            '+': np.array([1, 1]) / np.sqrt(2),
            '-': np.array([1, -1]) / np.sqrt(2)
        }
        psi1 = basis_states[qubit1]
        psi2 = basis_states[qubit2]
        amplitudes = np.kron(psi1, psi2)
        return QuantumState(amplitudes)
    
    def measure(self, basis_a: str = 'z', basis_b: str = 'z') -> Tuple[int, int]:
        """
        Measure both qubits in specified bases
        basis can be 'z' or 'x'
        Returns measurement results: (result_a, result_b) each 0 or 1
        """
        # Transform amplitudes to measurement basis if needed
        if basis_a == 'x':
            # Hadamard transform for qubit A
            H = np.array([[1, 1], [1, -1]]) / np.sqrt(2)
            self.amplitudes = np.kron(H, np.eye(2)) @ self.amplitudes
        
        if basis_b == 'x':
            # Hadamard transform for qubit B
            H = np.array([[1, 1], [1, -1]]) / np.sqrt(2)
            self.amplitudes = np.kron(np.eye(2), H) @ self.amplitudes
        
        # Calculate probabilities
        probabilities = np.abs(self.amplitudes) ** 2
        
        # Sample outcome
        outcome = np.random.choice(4, p=probabilities)
        result_a = (outcome >> 1) & 1  # First qubit
        result_b = outcome & 1           # Second qubit
        
        return result_a, result_b
    
    def correlation(self, num_measurements: int = 1000) -> float:
        """
        Calculate correlation coefficient for measurements in Z basis
        For maximally entangled states, should be -1 (perfect anti-correlation)
        """
        correlations = []
        for _ in range(num_measurements):
            state = QuantumState(self.amplitudes.copy())
            a, b = state.measure('z', 'z')
            # Correlation: +1 if same, -1 if different
            correlations.append(1 if a == b else -1)
        
        return np.mean(correlations)


class QuantumSimulator:
    """Quantum state simulator for DI-QKD protocols"""
    
    def __init__(self):
        self.initial_state = None
        self.history = []
    
    def create_bell_pair(self, state_type: str = 'phi_plus') -> QuantumState:
        """Create an entangled Bell pair"""
        self.initial_state = QuantumState.bell_state(state_type)
        return self.initial_state
    
    def create_separable_pair(self) -> QuantumState:
        """Create a separable (non-entangled) state"""
        self.initial_state = QuantumState.product_state('0', '0')
        return self.initial_state
    
    def simulate_bell_test(self, state: QuantumState, 
                          settings_a: List[str], 
                          settings_b: List[str],
                          num_runs: int = 1000) -> Dict:
        """
        Simulate CHSH Bell test measurements
        settings_a, settings_b: list of measurement bases ('x' or 'z')
        """
        results = {setting_a: {setting_b: {'same': 0, 'diff': 0} 
                              for setting_b in ['z', 'x']}
                   for setting_a in ['z', 'x']}
        
        for _ in range(num_runs):
            test_state = QuantumState(state.amplitudes.copy())
            for basis_a in ['z', 'x']:
                for basis_b in ['z', 'x']:
                    state_copy = QuantumState(state.amplitudes.copy())
                    result_a, result_b = state_copy.measure(basis_a, basis_b)
                    if result_a == result_b:
                        results[basis_a][basis_b]['same'] += 1
                    else:
                        results[basis_a][basis_b]['diff'] += 1
        
        return results
