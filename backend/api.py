"""
Flask Backend API for DI-QKD Simulator
Provides REST endpoints for the web frontend
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
from backend.diqkd_simulator import DIQKDSimulator
from backend.bb84 import BB84
from backend.chsh import CHSHBellTest
from backend.quantum_simulator import QuantumSimulator, QuantumState


app = Flask(__name__)
CORS(app)

# Global simulator instance
simulator = None


@app.route('/api/initialize', methods=['POST'])
def initialize_simulator():
    """Initialize a new DI-QKD simulator with given parameters"""
    global simulator
    
    try:
        data = request.json
        key_size = data.get('key_size', 512)
        chsh_rounds = data.get('chsh_rounds', 1000)
        
        simulator = DIQKDSimulator(key_size=key_size, num_chsh_rounds=chsh_rounds)
        
        return jsonify({
            'status': 'success',
            'message': 'Simulator initialized',
            'parameters': {
                'key_size': key_size,
                'chsh_rounds': chsh_rounds,
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@app.route('/api/run_bb84', methods=['POST'])
def run_bb84():
    """Run BB84 protocol"""
    global simulator
    
    if simulator is None:
        return jsonify({
            'status': 'error',
            'message': 'Simulator not initialized'
        }), 400
    
    try:
        results = simulator.run_bb84_protocol()
        
        return jsonify({
            'status': 'success',
            'results': {
                'initial_bits': results['initial_bits'],
                'sifted_key_length': results['sifted_key_length'],
                'final_key_length': results['final_key_length'],
                'qber': round(results['qber'], 6),
                'eve_detected': results['eve_detected'],
                'eve_error_rate': round(results['eve_error_rate'], 6),
                'statistics': results['statistics'],
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@app.route('/api/run_chsh', methods=['POST'])
def run_chsh():
    """Run CHSH Bell test"""
    global simulator
    
    if simulator is None:
        return jsonify({
            'status': 'error',
            'message': 'Simulator not initialized'
        }), 400
    
    try:
        data = request.json
        state_type = data.get('state_type', 'entangled')
        
        results = simulator.run_chsh_bell_test(state_type=state_type)
        
        return jsonify({
            'status': 'success',
            'results': {
                'chsh_value': round(results['chsh_value'], 6),
                'violates_bell': results['violates_bell'],
                'violation_margin': round(results['violation_margin'], 6),
                'quantum_advantage': round(results['quantum_advantage'], 6),
                'device_independent': results['device_independent'],
                'security_robustness': results['security_robustness'],
                'certified_key_rate': round(results['certified_key_rate'], 6),
                'min_entropy': round(results['min_entropy'], 6),
                'correlations': {
                    k: round(v, 6) if isinstance(v, float) else v
                    for k, v in results['correlations'].items()
                },
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@app.route('/api/run_full_simulation', methods=['POST'])
def run_full_simulation():
    """Run complete DI-QKD simulation"""
    global simulator
    
    if simulator is None:
        return jsonify({
            'status': 'error',
            'message': 'Simulator not initialized'
        }), 400
    
    try:
        data = request.json
        chsh_state = data.get('chsh_state', 'entangled')
        
        results = simulator.run_full_simulation(chsh_state=chsh_state)
        
        return jsonify({
            'status': 'success',
            'results': {
                'timestamp': results['timestamp'],
                'simulation_params': results['simulation_params'],
                'bb84_results': {
                    'initial_bits': results['bb84_results']['initial_bits'],
                    'sifted_key_length': results['bb84_results']['sifted_key_length'],
                    'final_key_length': results['bb84_results']['final_key_length'],
                    'qber': round(results['bb84_results']['qber'], 6),
                    'eve_detected': results['bb84_results']['eve_detected'],
                },
                'chsh_results': {
                    'chsh_value': round(results['chsh_results']['chsh_value'], 6),
                    'violates_bell': results['chsh_results']['violates_bell'],
                    'device_independent': results['chsh_results']['device_independent'],
                    'security_robustness': results['chsh_results']['security_robustness'],
                },
                'combined_key_length': len(results.get('combined_key', [])),
                'security_certification': results['security_certification'],
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@app.route('/api/get_execution_log', methods=['GET'])
def get_execution_log():
    """Get execution log from last simulation"""
    global simulator
    
    if simulator is None:
        return jsonify({
            'status': 'error',
            'message': 'No simulation executed yet'
        }), 400
    
    return jsonify({
        'status': 'success',
        'log': simulator.execution_log
    })


@app.route('/api/bell_state_test', methods=['POST'])
def bell_state_test():
    """Test different Bell states and measure correlations"""
    try:
        data = request.json
        state_type = data.get('state_type', 'phi_plus')
        num_measurements = data.get('num_measurements', 100)
        
        quantum_sim = QuantumSimulator()
        state = quantum_sim.create_bell_pair(state_type)
        correlation = state.correlation(num_measurements)
        
        return jsonify({
            'status': 'success',
            'bell_state': state_type,
            'num_measurements': num_measurements,
            'correlation': round(correlation, 6),
            'expected_correlation': -1.0,
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@app.route('/api/bb84_detailed', methods=['POST'])
def bb84_detailed():
    """Run detailed BB84 with step-by-step information"""
    try:
        data = request.json
        key_size = data.get('key_size', 256)
        
        bb84 = BB84(key_size=key_size)
        
        # Step by step execution
        alice_states = bb84.alice_prepare_states()
        bob_measurements = bb84.bob_measure_states()
        sifted_key = bb84.sift_keys()
        final_key, qber, test_positions = bb84.error_correction()
        amplified_key = bb84.privacy_amplification(final_key)
        eve_stats = bb84.simulate_eve_eavesdropping()
        
        # Prepare detailed response
        response = {
            'status': 'success',
            'key_size': key_size,
            'step1_alice_preparation': {
                'message': 'Alice prepared random bits in random bases',
                'bits_prepared': key_size,
                'sample_bases': bb84.alice_bases[:10],
                'sample_bits': bb84.alice_bits[:10],
            },
            'step2_bob_measurement': {
                'message': 'Bob measured in random bases',
                'bases_used': key_size,
                'sample_bases': bb84.bob_bases[:10],
                'sample_results': bb84.bob_measurements[:10],
            },
            'step3_sifting': {
                'message': 'Alice and Bob publicly compared bases',
                'sifted_key_length': len(sifted_key),
                'sift_ratio': round(len(sifted_key) / key_size, 4),
            },
            'step4_error_correction': {
                'message': 'Error correction and QBER assessment',
                'qber': round(qber, 6),
                'qber_secure': qber < 0.11,
                'test_bits': len(test_positions),
                'final_key_length': len(final_key),
            },
            'step5_privacy_amplification': {
                'message': 'Privacy amplification via XOR',
                'amplified_key_length': len(amplified_key),
            },
            'eve_eavesdropping': {
                'eve_detected': eve_stats['eve_detected'],
                'eve_error_rate': round(eve_stats['eve_error_rate'], 6),
            }
        }
        
        return jsonify(response)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@app.route('/api/chsh_detailed', methods=['POST'])
def chsh_detailed():
    """Run detailed CHSH with measurement details"""
    try:
        data = request.json
        num_rounds = data.get('num_rounds', 500)
        state_type = data.get('state_type', 'entangled')
        
        # Create quantum state
        quantum_sim = QuantumSimulator()
        if state_type == 'entangled':
            state = quantum_sim.create_bell_pair('phi_plus')
        else:
            state = quantum_sim.create_separable_pair()
        
        # Run CHSH
        chsh = CHSHBellTest(num_rounds=num_rounds)
        measurements = chsh.run_bell_test(state)
        stats = chsh.get_statistics()
        di_cert = chsh.device_independent_certification()
        
        response = {
            'status': 'success',
            'state_type': state_type,
            'num_rounds': num_rounds,
            'chsh_value': round(stats['chsh_value'], 6),
            'violates_bell': stats['violates_bell'],
            'violation_margin': round(stats['violation_margin'], 6),
            'quantum_advantage': round(stats['quantum_advantage'], 6),
            'classical_bound': 2.0,
            'correlations': {
                k: round(v, 6) if isinstance(v, float) else v
                for k, v in stats['correlations'].items()
            },
            'setting_distribution': stats['setting_distribution'],
            'device_independent': di_cert['device_independent'],
            'security_robustness': di_cert['security_robustness'],
            'certified_key_rate': round(di_cert['certified_key_rate'], 6),
            'min_entropy': round(di_cert['min_entropy'], 6),
        }
        
        return jsonify(response)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@app.route('/api/status', methods=['GET'])
def status():
    """Get current simulator status"""
    global simulator
    
    if simulator is None:
        return jsonify({
            'status': 'not_initialized',
            'message': 'Simulator not yet initialized'
        })
    
    return jsonify({
        'status': 'initialized',
        'has_results': simulator.results['bb84_results'] is not None,
        'execution_log_length': len(simulator.execution_log),
    })


@app.route('/api/reset', methods=['POST'])
def reset():
    """Reset simulator for new run"""
    global simulator
    
    if simulator is None:
        return jsonify({
            'status': 'error',
            'message': 'Simulator not initialized'
        }), 400
    
    simulator.reset()
    return jsonify({
        'status': 'success',
        'message': 'Simulator reset'
    })


@app.route('/api/export_results', methods=['GET'])
def export_results():
    """Export results to JSON"""
    global simulator
    
    if simulator is None:
        return jsonify({
            'status': 'error',
            'message': 'No results to export'
        }), 400
    
    try:
        filename = simulator.export_results()
        return jsonify({
            'status': 'success',
            'filename': filename
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'DI-QKD Simulator API'
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)
