# QKDT³ — Quantum Key Distribution with Triple-Hybrid TLS (ECDH + ML-KEM + QKD)
A comprehensive quantum-secured communication platform combining **BB84 + CHSH** quantum protocols, a **triple-hybrid TLS layer** (ECDH X25519 + ML-KEM-768 + QKD), and an **NS-3 network simulation** with realistic quantum/classical channel models.

---

## ✨ Features

### Quantum Protocols
- **BB84 Protocol** — Full QKD with basis sifting, error correction, and privacy amplification
- **CHSH Bell Test** — Device-independent security certification via Bell inequality violation
- **Eve Eavesdropping Detection** — QBER monitoring with intercept-resend attack simulation

### Triple-Hybrid TLS Layer
- **Real-Socket TLS** — Production-like encrypted communication over TCP
- **ECDH X25519** — Classical elliptic-curve key exchange
- **ML-KEM-768** — Post-quantum lattice-based key encapsulation (NIST FIPS 203)
- **QKD Key Injection** — Quantum-derived keys mixed into the handshake
- **AES-256-GCM** — Authenticated record-layer encryption with per-record nonces

### NS-3 Network Simulation
- **Quantum Channel Model** — Fiber attenuation (0.2 dB/km), depolarization, dark counts, detector efficiency
- **Classical Channel Model** — Latency, jitter, packet loss, bandwidth limiting
- **Eavesdropper Channel** — Intercept-resend attack with tunable intercept rate
- **7 Pre-built Scenarios** — Metro fiber, intercity, LEO satellite, eavesdropper, distance sweep, metro ring
- **Visualization** — Dark-themed matplotlib plots for key rate, QBER, handshake timing

### Web Interface & API
- **Flask REST API** — Full protocol execution and result export
- **Interactive Web UI** — Run simulations from the browser
- **ML-KEM-768** — Post-quantum cryptography module

---

## 📁 Project Structure

```
code-2/
├── backend/
│   ├── quantum_simulator.py      # Quantum state simulation (Bell pairs, measurement)
│   ├── bb84.py                   # BB84 protocol implementation
│   ├── chsh.py                   # CHSH Bell test implementation
│   ├── diqkd_simulator.py        # Main DI-QKD orchestrator
│   └── api.py                    # Flask REST API
├── tls/                          # ⭐ Triple-Hybrid TLS Layer
│   ├── __init__.py               # Package exports
│   ├── prf.py                    # HKDF-SHA256 key schedule
│   ├── hybrid_kex.py             # ECDH + ML-KEM-768 + QKD key exchange
│   ├── record.py                 # AES-256-GCM record encryption/decryption
│   ├── handshake.py              # ClientHello / ServerHello / Finished messages
│   ├── session.py                # Socket wrapper (send/recv over TLS)
│   ├── tls_server.py             # TLS-wrapped Flask server
│   └── tls_client.py             # CLI/library TLS client
├── ns3_sim/                      # ⭐ NS-3 Network Simulation
│   ├── __init__.py               # Package exports
│   ├── channel_model.py          # Quantum + Classical + Eavesdropper channels
│   ├── topology.py               # Network topologies (P2P, star, ring)
│   ├── qkd_application.py        # QKD protocol over simulated channels
│   ├── tls_application.py        # TLS handshake timing simulation
│   ├── scenarios.py              # 7 pre-built simulation scenarios
│   ├── metrics.py                # Data collection + CSV/JSON export
│   └── visualizer.py             # Matplotlib plots (dark theme)
├── frontend/
│   ├── index.html                # Web UI
│   └── app.js                    # Frontend JavaScript
├── tests/
│   ├── test_tls.py               # TLS layer test suite (26 tests)
│   └── test_ns3_sim.py           # NS-3 simulation test suite (39 tests)
├── ml_kem.py                     # ML-KEM post-quantum key encapsulation
├── ml_kem_768.py                 # ML-KEM-768 implementation
├── demo.py                       # Original QKD demo
├── demo_tls_ns3.py               # ⭐ Full TLS + NS-3 demo (6 scenarios)
├── test_simulator.py             # Original simulator tests
├── requirements.txt              # Python dependencies
└── ARCHITECTURE.md               # Detailed architecture documentation
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip package manager

### Installation

```bash
# Clone or navigate to the project
cd code-2

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Run the Full Demo

```bash
python demo_tls_ns3.py
```

This runs 6 simulation scenarios in ~1 second:
1. **Channel Models** — Key rate vs distance for 1–200 km fiber
2. **QKD over Fiber** — BB84 + CHSH over 10 km simulated fiber
3. **TLS Handshake** — Timing breakdown of triple-hybrid handshake
4. **Eavesdropper Detection** — QBER rise with increasing intercept rates
5. **Distance Sweep** — Key rate decay analysis with visualization
6. **Available Scenarios** — List of all pre-built simulation configs

### Start the TLS Server

```bash
# Terminal 1: Start the TLS-wrapped Flask server
python -m tls.tls_server

# Terminal 2: Connect with the TLS client
python -m tls.tls_client
```

### Start the Web UI

```bash
# Start Flask backend
python -m backend.api

# Serve frontend (in another terminal)
python -m http.server 8000 --directory frontend
# Visit http://localhost:8000
```

### Run Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run TLS tests only
python -m pytest tests/test_tls.py -v

# Run NS-3 simulation tests only
python -m pytest tests/test_ns3_sim.py -v

# Run original simulator tests
python -m pytest test_simulator.py -v
```

---

## 🔐 Architecture

### Triple-Hybrid TLS Handshake

```
┌────────────────────────────────────────────────────────────┐
│                    TLS Handshake Flow                       │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Client                                     Server         │
│    │                                          │            │
│    │──── ClientHello ─────────────────────────►│            │
│    │     (ECDH pub + ML-KEM pub + QKD flag)   │            │
│    │                                          │            │
│    │◄─── ServerHello ─────────────────────────│            │
│    │     (ECDH pub + ML-KEM ciphertext)       │            │
│    │                                          │            │
│    │     ┌─────────────────────────────┐      │            │
│    │     │  shared_secret = HKDF(      │      │            │
│    │     │    ECDH_shared ‖            │      │            │
│    │     │    SHA256(ML-KEM_ct) ‖      │      │            │
│    │     │    QKD_key                  │      │            │
│    │     │  )                          │      │            │
│    │     └─────────────────────────────┘      │            │
│    │                                          │            │
│    │◄─── Server Finished (HMAC) ──────────────│            │
│    │──── Client Finished (HMAC) ──────────────►│            │
│    │                                          │            │
│    │◄═══ AES-256-GCM Encrypted Data ═════════►│            │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

**Security guarantee:** The combined secret is secure as long as **at least one** of the three components (ECDH, ML-KEM, QKD) remains unbroken.

### Network Simulation Pipeline

```
┌──────────┐    Quantum Channel    ┌──────────┐
│  Alice   │◄─────────────────────►│   Bob    │
│ (QKD TX) │  fiber loss, noise,   │ (QKD RX) │
│          │  depolarization       │          │
└────┬─────┘                       └────┬─────┘
     │       Classical Channel          │
     └──────────────────────────────────┘
              latency, jitter,
              packet loss
              
         Eve (optional)
         ├── intercept-resend attack
         └── detectable via QBER > 11%
```

---

## 📊 Simulation Scenarios

| Scenario | Description | Distance | Key Use Case |
|----------|-------------|----------|-------------|
| `fiber_10km` | Metro fiber QKD | 10 km | City-scale secure links |
| `fiber_50km` | Intercity fiber | 50 km | Regional connections |
| `fiber_100km` | Long-distance fiber | 100 km | Near detection limit |
| `satellite_leo` | LEO satellite link | 600 km × 2 | Global QKD coverage |
| `eve_attack` | Eavesdropper scenario | 20 km | Security validation |
| `distance_sweep` | Key rate analysis | 1–200 km | Performance benchmarking |
| `metro_ring` | Ring network | 40 km circumf. | Metro QKD network |

### Using Scenarios Programmatically

```python
from ns3_sim.scenarios import get_scenario
from ns3_sim.qkd_application import QKDApplication

# Load a pre-built scenario
config = get_scenario("fiber_10km")
topo = config['topology']

# Run QKD over simulated network
app = QKDApplication(topo)
result = app.run_full_qkd("alice-bob", key_size=512, chsh_rounds=1000)

print(f"Security: {result['security_level']}")
print(f"QBER: {result['bb84']['effective_qber']}")
print(f"Key length: {result['bb84']['final_key_length']} bits")
```

---

## 💻 Code Examples

### Using the DI-QKD Simulator

```python
from backend.diqkd_simulator import DIQKDSimulator

simulator = DIQKDSimulator(key_size=512, num_chsh_rounds=1000)
results = simulator.run_full_simulation(chsh_state='entangled')

print("BB84 QBER:", results['bb84_results']['qber'])
print("CHSH Value:", results['chsh_results']['chsh_value'])
print("Security:", results['security_certification']['overall_security_level'])
```

### Running TLS with QKD Key Injection

```python
from tls.hybrid_kex import HybridKeyExchange, bits_to_bytes
from backend.diqkd_simulator import DIQKDSimulator

# Generate QKD key
sim = DIQKDSimulator(key_size=256)
results = sim.run_full_simulation()
qkd_key = bits_to_bytes(results['combined_key'])

# Use in TLS handshake
kex = HybridKeyExchange()
client_shares = kex.generate_client_shares()
# ... send to server, receive response, derive shared secret
```

### Simulating Channel Effects

```python
from ns3_sim.channel_model import QuantumChannel, EavesdropperChannel

# Normal fiber channel
qc = QuantumChannel(distance_km=50.0)
print(f"Key rate: {qc.key_rate_per_pulse:.8f} bits/pulse")
print(f"Expected QBER: {qc.expected_qber:.4f}")

# Channel with eavesdropper
ec = EavesdropperChannel(distance_km=20.0, intercept_rate=0.5)
print(f"QBER with Eve: {ec.expected_qber:.4f}")  # > 11% = detected!
```

### TLS Handshake Timing Analysis

```python
from ns3_sim.topology import QKDTopology
from ns3_sim.tls_application import TLSApplication

topo = QKDTopology.create_point_to_point(distance_km=100.0)
app = TLSApplication(topo)

result = app.simulate_full_session("alice-bob", include_qkd=True)
print(f"Handshake: {result['time_to_first_byte_ms']:.2f} ms")
print(f"Total session: {result['total_session_ms']:.2f} ms")
```

---

## 🔧 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/initialize` | Initialize simulator with parameters |
| `POST` | `/api/run_bb84` | Run BB84 protocol |
| `POST` | `/api/run_chsh` | Run CHSH Bell test |
| `POST` | `/api/run_full_simulation` | Run complete DI-QKD |
| `POST` | `/api/reset` | Reset simulator |
| `GET` | `/api/get_execution_log` | Get execution log |
| `GET` | `/api/export_results` | Export results to JSON |
| `GET` | `/health` | Health check |
| `POST` | `/api/bb84_detailed` | Detailed BB84 step-by-step |
| `POST` | `/api/chsh_detailed` | Detailed CHSH measurements |

---

## 📈 Key Metrics

| Metric | Description | Secure Threshold |
|--------|-------------|-----------------|
| QBER | Quantum Bit Error Rate | < 11% |
| CHSH Value | Bell test statistic | > 2.0 (violation) |
| Sift Efficiency | Ratio sifted/sent bits | ~50% |
| Key Rate | Secure bits per pulse | > 0 |
| Detection Rate | Photons detected/sent | Distance-dependent |

### Security Levels

| Level | Condition |
|-------|-----------|
| **Very High** (DI Certified) | CHSH > 2.4, QBER < 11%, no Eve |
| **High** | CHSH > 2.1, QBER < 11% |
| **Medium** | CHSH > 2.0, QBER < 13% |
| **Medium-High** | QBER < 11%, no DI certification |
| **Low** | QBER > 11% or CHSH ≤ 2 |

---

## 🧪 Test Coverage

| Test Suite | Tests | Coverage |
|-----------|-------|---------|
| `tests/test_tls.py` | 26 | HKDF, hybrid KEX, AES-GCM record layer, handshake serialization, end-to-end TLS session |
| `tests/test_ns3_sim.py` | 39 | Quantum/classical channels, topologies, scenarios, metrics, QKD & TLS applications |
| `test_simulator.py` | 20 | Quantum states, BB84, CHSH, DI-QKD integration |

---

## 📖 References

- Bennett, C. H., & Brassard, G. (1984). *Quantum cryptography: Public key distribution and coin tossing*
- Clauser, J. F., et al. (1969). *Proposed Experiment to Test Local Hidden-Variable Theories*
- NIST FIPS 203: Module-Lattice-Based Key-Encapsulation Mechanism Standard (ML-KEM)
- draft-ietf-tls-hybrid-design: Hybrid Key Exchange in TLS 1.3
- Langley, A. (2018). *Post-quantum key exchange with X25519 and ML-KEM*

---

## 🛠️ Troubleshooting

| Error | Solution |
|-------|---------|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| `Cannot connect to API` | Ensure Flask is running: `python -m backend.api` |
| `Address already in use` | Change port in `api.py` or kill the process on port 5000/8443 |
| `ML-KEM IndexError` | Retry logic handles this automatically (see `hybrid_kex.py`) |
| `Server Finished verification failed` | Ensure client and server use the **same** QKD key bytes |

---

## 📦 Dependencies

```
Flask==3.0.0
Flask-CORS==4.0.0
numpy==1.24.3
pytest==7.4.0
Werkzeug==3.0.0
cryptography>=41.0.0    # X25519 ECDH, AES-256-GCM, HKDF
matplotlib>=3.7.0       # Simulation visualization
```

---

## 📝 License

This project is for educational and research purposes.

## 👨‍💻 Contributing

For improvements and bug reports, please feel free to modify and extend the simulator.

---

**Last Updated**: 2026-04-13
**Version**: 2.0
**Status**: Production Ready — TLS + NS-3 Integrated
#   D I - Q K D - S i m u l a t o r - w i t h - H y b r i d - T L S - L a y e r  
 #   D I - Q K D - S i m u l a t o r - w i t h - H y b r i d - T L S - L a y e r  
 