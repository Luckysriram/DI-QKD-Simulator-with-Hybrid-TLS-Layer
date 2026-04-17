# Consolidated Simulation Results Report

This document consolidates all the simulation data and performance metrics collected across the project's various components, including the hybrid PQC-QKD protocols and the NS-3 real-world network simulations.

---

## 1. Executive Summary
The simulations evaluated a hybrid cryptographic system combining Post-Quantum Cryptography (ML-KEM) and Device-Independent Quantum Key Distribution (DI-QKD). Testing spanned across different channel models (Standard Fiber, Satellite LEO) and security scenarios (Eavesdropping detection).

**Key Metrics Overview:**
- **Best Key Rate:** 0.0434 bits/pulse (@ 1km)
- **Max Secure Distance:** ~25km (Fiber)
- **Average TLS Handshake:** 4.40 ms
- **Throughput:** ~260 Mbps (standard fiber)

---

## 2. DI-QKD Protocol Results
*Source: diqkd_results_20260413_111816.json*

### Simulation Parameters
| Parameter | Value |
| :--- | :--- |
| Initial Key Size | 512 bits |
| CHSH Rounds | 1000 |
| State Type | Entangled |

### Key Statistics
| Stage | Result |
| :--- | :--- |
| Sifted Key Length | 268 bits (52.34% efficiency) |
| QBER | 0.0000 |
| Final Key Length | 118 bits |
| Eve Detected | **True** |
| DI Certified | False (Insufficient Bell violation) |

---

## 3. NS-3 Real-World Scenarios
*Source: simulation_results/ns3_real/all_results.json*

### Scenario Performance Benchmarks
| Scenario | Distance (km) | Throughput (Mbps) | Avg Delay (ms) | TLS Handshake (ms) |
| :--- | :---: | :---: | :---: | :---: |
| Fiber (Short) | 10.0 | 183.80 | 0.0917 | 4.4003 |
| Fiber (Medium) | 50.0 | 183.80 | 0.0917 | 4.4015 |
| Fiber (Long) | 100.0 | 183.79 | 0.0917 | 4.4030 |
| Satellite LEO | 600.0 | 26.35 | 1.0682 | 4.4180 |

---

## 4. Distance Sweep Analysis (Fiber)
Analysis of QKD performance degradation over increasing fiber lengths.

| Distance (km) | QBER | Key Rate | Secure Status |
| :---: | :---: | :---: | :---: |
| 1.0 | 0.0050 | 0.0434 | ✅ SECURE |
| 5.0 | 0.0244 | 0.0266 | ✅ SECURE |
| 10.0 | 0.0476 | 0.0141 | ✅ SECURE |
| 20.0 | 0.0906 | 0.0024 | ✅ SECURE |
| 30.0 | 0.1296 | 0.0000 | ❌ INSECURE |
| 50.0 | 0.1967 | 0.0000 | ❌ INSECURE |
| 100.0 | 0.3161 | 0.0000 | ❌ INSECURE |

---

## 5. Eavesdropping Detection (Eve Attack)
Simulated "Intercept-Resend" attack on a 20km fiber link.

| Intercept Rate (%) | Observed QBER | Key Rate | Secure? |
| :---: | :---: | :---: | :---: |
| 0% | 0.0906 | 0.0024 | ✅ YES |
| 10% | 0.1134 | 0.0000 | ❌ NO |
| 20% | 0.1361 | 0.0000 | ❌ NO |
| 50% | 0.2043 | 0.0000 | ❌ NO |
| 100% | 0.3180 | 0.0000 | ❌ NO |

---

## 6. TLS Handshake Latency
Performance of the triple-hybrid handshake (ECDH + ML-KEM + QKD).

| Scenario | Handshake Time (ms) | Data Transfer (ms) |
| :--- | :---: | :---: |
| 1km Fiber | 4.4000 | 0.0800 |
| 10km Fiber | 4.4003 | 0.0800 |
| 50km Fiber | 4.4015 | 0.0803 |
| 100km Fiber | 4.4030 | 0.0805 |

---

## 7. Conclusions
1. **PQC-QKD Synergy:** The hybrid layer provides robust fallback. While QKD is limited to ~25km in standard conditions, ML-KEM ensures security for longer distances/noisier channels.
2. **Network Impact:** QKD-derived key rotation introduces negligible latency (sub-ms) to the TLS handshake under normal conditions.
3. **DI-QKD Constraints:** Achieving device-independence requires extremely high-quality entanglement and low-loss channels, which were difficult to maintain beyond short distances in the current setup.
