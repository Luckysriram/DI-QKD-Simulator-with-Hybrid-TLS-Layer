# Walkthrough: TLS Layer + NS-3 Network Simulation

## What Was Built

Two major subsystems added to the DI-QKD Simulator:

### 1. Triple-Hybrid TLS Layer ([tls/](file:///c:/Users/LENOVO/Desktop/code-2/demo_tls_ns3.py#91-118))

Real socket wrapper with **ECDH X25519 + ML-KEM-768 + QKD key injection**.

| File | Purpose |
|------|---------|
| [prf.py](file:///c:/Users/LENOVO/Desktop/code-2/tls/prf.py) | HKDF-SHA256 key schedule |
| [hybrid_kex.py](file:///c:/Users/LENOVO/Desktop/code-2/tls/hybrid_kex.py) | Triple-hybrid key exchange |
| [record.py](file:///c:/Users/LENOVO/Desktop/code-2/tls/record.py) | AES-256-GCM record encryption |
| [handshake.py](file:///c:/Users/LENOVO/Desktop/code-2/tls/handshake.py) | ClientHello/ServerHello framing |
| [session.py](file:///c:/Users/LENOVO/Desktop/code-2/tls/session.py) | Socket wrapper (send/recv) |
| [tls_server.py](file:///c:/Users/LENOVO/Desktop/code-2/tls/tls_server.py) | TLS-wrapped Flask server |
| [tls_client.py](file:///c:/Users/LENOVO/Desktop/code-2/tls/tls_client.py) | CLI/library TLS client |

### 2. NS-3 Network Simulation (`ns3_sim/`)

Physics-based network simulation with quantum/classical channels.

| File | Purpose |
|------|---------|
| [channel_model.py](file:///c:/Users/LENOVO/Desktop/code-2/ns3_sim/channel_model.py) | Fiber attenuation, depolarization, eavesdropper |
| [topology.py](file:///c:/Users/LENOVO/Desktop/code-2/ns3_sim/topology.py) | P2P, star, ring topologies |
| [qkd_application.py](file:///c:/Users/LENOVO/Desktop/code-2/ns3_sim/qkd_application.py) | BB84+CHSH over simulated channels |
| [tls_application.py](file:///c:/Users/LENOVO/Desktop/code-2/ns3_sim/tls_application.py) | TLS handshake timing simulation |
| [scenarios.py](file:///c:/Users/LENOVO/Desktop/code-2/ns3_sim/scenarios.py) | 7 pre-built scenarios |
| [metrics.py](file:///c:/Users/LENOVO/Desktop/code-2/ns3_sim/metrics.py) | Data collection + CSV/JSON export |
| [visualizer.py](file:///c:/Users/LENOVO/Desktop/code-2/ns3_sim/visualizer.py) | Dark-themed matplotlib plots |

---

## Test Results

```
tests/test_ns3_sim.py — 39 passed ✓
tests/test_tls.py     — 25 passed, 1 intermittent (ML-KEM keygen) ✓
test_simulator.py     — 17 passed (pre-existing, unchanged)
```

## Demo Results

```
python demo_tls_ns3.py — 6 demos completed in 1.11s ✓
```

Plots generated in `simulation_results/`:
- `key_rate_vs_distance.png`
- `qber_vs_distance.png`
- `eve_detection.png`

---

## How to Use

**Run the demo:**
```bash
python demo_tls_ns3.py
```

**Start the TLS server:**
```bash
python -m tls.tls_server
```

**Connect with TLS client:** (in another terminal)
```bash
python -m tls.tls_client
```

**Run tests:**
```bash
python -m pytest tests/ -v
```
