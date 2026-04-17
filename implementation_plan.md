# TLS Layer + NS-3 Network Simulation — Implementation Plan

## Goal

Add two major subsystems to the DI-QKD Simulator:

1. **Real-socket TLS layer** with **triple-hybrid key exchange** (ECDH X25519 + ML-KEM-768 + QKD key injection) and AES-256-GCM record encryption
2. **NS-3 network simulation** modeling quantum/classical channels with realistic loss, latency, and eavesdropping scenarios

---

## Proposed Changes

### TLS Layer (`tls/`)

#### [NEW] [\_\_init\_\_.py](file:///c:/Users/LENOVO/Desktop/code-2/tls/__init__.py)
Package init — exports `TLSServer`, `TLSClient`, `TLSSession`.

---

#### [NEW] [prf.py](file:///c:/Users/LENOVO/Desktop/code-2/tls/prf.py)
HKDF-SHA256 key schedule:
- `hkdf_extract(salt, ikm)` → PRK
- `hkdf_expand(prk, info, length)` → OKM
- `derive_traffic_keys(shared_secret, transcript_hash)` → [(client_key, server_key, client_iv, server_iv)](file:///c:/Users/LENOVO/Desktop/code-2/ml_kem.py#87-100) for AES-256-GCM

Uses `cryptography.hazmat.primitives.kdf.hkdf`.

---

#### [NEW] [hybrid_kex.py](file:///c:/Users/LENOVO/Desktop/code-2/tls/hybrid_kex.py)
Triple-hybrid key exchange:
- **ECDH**: X25519 via `cryptography.hazmat.primitives.asymmetric.x25519`
- **ML-KEM-768**: Reuse existing [ml_kem.py](file:///c:/Users/LENOVO/Desktop/code-2/ml_kem.py) ([ml_kem_keygen](file:///c:/Users/LENOVO/Desktop/code-2/ml_kem_768.py#259-267), [ml_kem_encapsulate](file:///c:/Users/LENOVO/Desktop/code-2/ml_kem_768.py#268-275), [ml_kem_decapsulate](file:///c:/Users/LENOVO/Desktop/code-2/ml_kem.py#328-348))
- **QKD key injection**: Accept optional QKD-derived key bytes from DI-QKD simulation

Key classes/functions:
- `HybridKeyExchange` class — orchestrates all three components
  - `generate_client_shares()` → [(ecdh_public, mlkem_public, client_private_state)](file:///c:/Users/LENOVO/Desktop/code-2/ml_kem.py#87-100)
  - `server_respond(ecdh_client_pub, mlkem_client_pub, qkd_key=None)` → [(ecdh_server_pub, mlkem_ciphertext, shared_secret)](file:///c:/Users/LENOVO/Desktop/code-2/ml_kem.py#87-100)
  - `client_derive(server_ecdh_pub, mlkem_ciphertext, client_state, qkd_key=None)` → `shared_secret`
- Final shared secret = `HKDF(ECDH_shared ‖ ML-KEM_shared ‖ QKD_key)`

---

#### [NEW] [record.py](file:///c:/Users/LENOVO/Desktop/code-2/tls/record.py)
TLS record layer:
- `RecordLayer` class with [encrypt(plaintext, record_type)](file:///c:/Users/LENOVO/Desktop/code-2/ml_kem_768.py#218-242) and [decrypt(ciphertext)](file:///c:/Users/LENOVO/Desktop/code-2/ml_kem_768.py#243-257) 
- AES-256-GCM with 12-byte nonce (4-byte fixed IV + 8-byte counter)
- AAD = record type (1 byte) + length (2 bytes)
- Max record size = 16384 bytes (TLS 1.3 limit), fragmentation for larger data

---

#### [NEW] [handshake.py](file:///c:/Users/LENOVO/Desktop/code-2/tls/handshake.py)
TLS-style handshake message framing:
- `ClientHello`: protocol version, ECDH public key, ML-KEM public key, random nonce
- `ServerHello`: ECDH public key, ML-KEM ciphertext, random nonce, encrypted certificate
- `Finished`: HMAC of handshake transcript (verifies key derivation)
- Serialization via `struct` (length-prefixed binary format)

---

#### [NEW] [session.py](file:///c:/Users/LENOVO/Desktop/code-2/tls/session.py)
Real socket wrapper:
- `TLSSession(sock, is_server, qkd_key=None)` — wraps a `socket.socket`
- `handshake()` — performs full ClientHello/ServerHello/Finished exchange
- `send(data)` → encrypts via record layer, writes to socket
- `recv()` → reads from socket, decrypts via record layer
- `close()` → sends close_notify, closes socket

---

#### [NEW] [tls_server.py](file:///c:/Users/LENOVO/Desktop/code-2/tls/tls_server.py)
TLS-wrapped Flask server:
- Starts a TCP `socket.listen()` server
- For each connection: performs TLS handshake, then proxies decrypted HTTP to Flask's WSGI app
- `TLSFlaskServer(app, host, port, qkd_key=None)` — integrates with DI-QKD key
- Spawns threads per connection

---

#### [NEW] [tls_client.py](file:///c:/Users/LENOVO/Desktop/code-2/tls/tls_client.py)
CLI + library client:
- `TLSClient(host, port, qkd_key=None)` 
- `connect()` → TCP connect + TLS handshake
- `request(method, path, json=None)` → sends HTTP request over TLS, returns response
- Standalone demo: connects to TLS server, runs `/api/run_full_simulation`

---

### NS-3 Network Simulation (`ns3_sim/`)

> [!IMPORTANT]
> NS-3 requires a separate installation. The simulation module is designed as a **Python wrapper** that generates NS-3 C++ simulation scripts and parses their output. If NS-3 is not installed, it falls back to a built-in Python discrete-event simulator.

#### [NEW] [\_\_init\_\_.py](file:///c:/Users/LENOVO/Desktop/code-2/ns3_sim/__init__.py)
Package init.

---

#### [NEW] [channel_model.py](file:///c:/Users/LENOVO/Desktop/code-2/ns3_sim/channel_model.py)
Channel models for simulation:
- `QuantumChannel`: fiber loss (0.2 dB/km), depolarization noise, photon detection efficiency, distance-based QBER
- `ClassicalChannel`: configurable latency, jitter (Gaussian), packet loss rate, bandwidth limit
- `EavesdropperChannel`: extends QuantumChannel — Eve intercepts N% of photons

---

#### [NEW] [topology.py](file:///c:/Users/LENOVO/Desktop/code-2/ns3_sim/topology.py)
Network topology:
- `QKDTopology` class — creates NS-3 nodes and links
- `create_point_to_point(alice, bob, distance_km)` — simple fiber link
- `create_with_eve(alice, bob, eve_position_km)` — adds eavesdropper node
- `create_metro_ring(nodes, distances)` — ring topology for urban QKD
- Each link has both a quantum and classical channel

---

#### [NEW] [qkd_application.py](file:///c:/Users/LENOVO/Desktop/code-2/ns3_sim/qkd_application.py)
NS-3 application for QKD:
- Runs BB84 protocol over simulated quantum channel
- Runs CHSH verification over simulated link
- Collects per-round metrics: QBER, key rate, photon counts
- Calls into existing [backend/bb84.py](file:///c:/Users/LENOVO/Desktop/code-2/backend/bb84.py) and [backend/chsh.py](file:///c:/Users/LENOVO/Desktop/code-2/backend/chsh.py) with channel model applied

---

#### [NEW] [tls_application.py](file:///c:/Users/LENOVO/Desktop/code-2/ns3_sim/tls_application.py)
NS-3 application for TLS:
- Runs hybrid TLS handshake over simulated TCP link
- Measures handshake time, throughput, overhead from PQ crypto
- Uses `tls/` module for actual crypto operations

---

#### [NEW] [scenarios.py](file:///c:/Users/LENOVO/Desktop/code-2/ns3_sim/scenarios.py)
Pre-built simulation scenarios:
- `fiber_10km()` — short-distance metro QKD
- `fiber_100km()` — inter-city QKD
- `satellite_leo()` — LEO satellite link (600km, free-space loss)
- `eve_attack(distance, intercept_rate)` — eavesdropper scenario
- Each returns a configured `QKDTopology` + channel parameters

---

#### [NEW] [metrics.py](file:///c:/Users/LENOVO/Desktop/code-2/ns3_sim/metrics.py)
Metrics collection and analysis:
- `MetricsCollector` class — records time-series data during simulation
- Key metrics: key generation rate, QBER vs distance, TLS handshake latency, throughput, packet loss impact
- `summary()` → dict of aggregated statistics
- `to_csv(filename)` → export for external analysis

---

#### [NEW] [visualizer.py](file:///c:/Users/LENOVO/Desktop/code-2/ns3_sim/visualizer.py)
Matplotlib visualization:
- `plot_key_rate_vs_distance()` — key rate decay with fiber length
- `plot_qber_vs_noise()` — QBER under different noise levels
- `plot_tls_handshake_breakdown()` — timing of ECDH / ML-KEM / QKD components
- `plot_throughput()` — encrypted data throughput
- `generate_report(metrics, output_dir)` — saves all plots as PNGs

---

### Tests

#### [NEW] [tests/test_tls.py](file:///c:/Users/LENOVO/Desktop/code-2/tests/test_tls.py)
- `TestHKDF`: verify key derivation produces expected lengths
- `TestHybridKEX`: test ECDH-only, ML-KEM-only, and triple-hybrid key agreement
- `TestRecordLayer`: encrypt/decrypt roundtrip, tamper detection
- `TestHandshake`: serialize/deserialize ClientHello/ServerHello
- `TestTLSSession`: end-to-end socket test (loopback) with real send/recv
- `TestQKDInjection`: verify QKD key changes derived secret

#### [NEW] [tests/test_ns3_sim.py](file:///c:/Users/LENOVO/Desktop/code-2/tests/test_ns3_sim.py)
- `TestQuantumChannel`: verify loss model, QBER calculation, attenuation
- `TestClassicalChannel`: verify latency, jitter, packet loss
- `TestTopology`: create topologies, verify node counts and link parameters
- `TestScenarios`: run each scenario, verify metrics are collected
- `TestMetrics`: verify aggregation and CSV export

---

### Updates to Existing Files

#### [MODIFY] [requirements.txt](file:///c:/Users/LENOVO/Desktop/code-2/requirements.txt)
Add:
```
cryptography>=41.0.0
matplotlib>=3.7.0
```

#### [MODIFY] [api.py](file:///c:/Users/LENOVO/Desktop/code-2/backend/api.py)
Add endpoints:
- `POST /api/tls/status` — show TLS session info (cipher, KEX type, key sources)
- `POST /api/ns3/run_scenario` — run an NS-3 scenario and return metrics
- `GET /api/ns3/scenarios` — list available scenarios

---

## Verification Plan

### Automated Tests

**Run TLS tests:**
```bash
cd c:\Users\LENOVO\Desktop\code-2
python -m pytest tests/test_tls.py -v
```

**Run NS-3 simulation tests:**
```bash
cd c:\Users\LENOVO\Desktop\code-2
python -m pytest tests/test_ns3_sim.py -v
```

**Run existing test suite (regression):**
```bash
cd c:\Users\LENOVO\Desktop\code-2
python -m pytest test_simulator.py -v
```

### Integration Tests

**TLS end-to-end test (included in `tests/test_tls.py::TestTLSSession`):**
1. Start TLS server on localhost in a thread
2. Connect TLS client
3. Send a JSON payload, receive encrypted response
4. Verify decrypted response matches expected
5. Verify QKD key injection changes the session key

**NS-3 full pipeline test (included in `tests/test_ns3_sim.py`):**
1. Create a fiber_10km scenario
2. Run QKD application → collect key
3. Run TLS application with QKD key → verify handshake succeeds
4. Verify metrics are collected and within expected bounds

### Manual Verification

**TLS demo (after implementation):**
1. Run `python -m tls.tls_server` in one terminal
2. Run `python -m tls.tls_client` in another terminal
3. Observe: handshake log showing ECDH + ML-KEM + QKD components
4. Observe: encrypted API response returned correctly

**NS-3 demo:**
1. Run `python demo_tls_ns3.py`
2. Observe: simulation runs for each scenario
3. Observe: matplotlib charts saved showing key rate vs distance, QBER, etc.
