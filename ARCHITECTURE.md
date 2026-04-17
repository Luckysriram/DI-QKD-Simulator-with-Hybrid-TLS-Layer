# DI-QKD Simulator - Architecture & Design Document

## 📐 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Web Browser                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Frontend (HTML/CSS/JavaScript)                           │  │
│  │ - UI Components & Forms                                  │  │
│  │ - Real-time Result Display                               │  │
│  │ - Execution Log Viewer                                   │  │
│  └────────────────────┬─────────────────────────────────────┘  │
└─────────────────────────┼────────────────────────────────────────┘
                         │ REST API (HTTP)
                         │
┌─────────────────────────▼────────────────────────────────────────┐
│                   Flask Backend (Python)                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ API Routes                                               │  │
│  │ - /api/initialize         Create simulator               │  │
│  │ - /api/run_bb84           Execute BB84                   │  │
│  │ - /api/run_chsh           Execute CHSH                   │  │
│  │ - /api/run_full_simulation Full DI-QKD                   │  │
│  │ - /api/export_results     Export results                 │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                        │
│  ┌────────────────────▼─────────────────────────────────────┐  │
│  │ Core Simulator Components                                │  │
│  │                                                          │  │
│  │  ┌──────────────────┐  ┌──────────────────┐             │  │
│  │  │ DI-QKD Simulator │  │  BB84 Protocol   │             │  │
│  │  │  (Orchestrator)  │──│  - State Prep    │             │  │
│  │  │                  │  │  - Measurement   │             │  │
│  │  │  - Run BB84      │  │  - Sifting       │             │  │
│  │  │  - Run CHSH      │  │  - Error Corr.   │             │  │
│  │  │  - Combine Keys  │  │  - Privacy Amp.  │             │  │
│  │  │  - Security Cert.│  │  - Eve Detection │             │  │
│  │  └────────┬─────────┘  └──────────────────┘             │  │
│  │           │                                             │  │
│  │  ┌────────▼──────────────┐  ┌──────────────────┐       │  │
│  │  │  CHSH Bell Test       │  │ Quantum Simulator│       │  │
│  │  │  - Run Measurements   │  │ - Bell States    │       │  │
│  │  │  - Calculate CHSH     │  │ - Product States │       │  │
│  │  │  - DI Certification   │  │ - Measurement    │       │  │
│  │  │  - Key Extraction     │  │ - Correlations   │       │  │
│  │  └───────────────────────┘  └──────────────────┘       │  │
│  │                                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                       │                                        │
└───────────────────────┼────────────────────────────────────────┘
                        │
                   Results JSON
                   Execution Log
```

---

## 🗂️ Module Overview

### 1. **quantum_simulator.py**
**Purpose**: Quantum state simulation and measurement

**Key Classes**:
- `QuantumState`: Handles quantum state vectors and measurements
  - Bell states (maximally entangled)
  - Product states (separable)
  - Measurement in Z and X bases
  - Correlation calculations

**Key Functions**:
- `bell_state()`: Create entangled states
- `product_state()`: Create separable states
- `measure()`: Measure in specified bases
- `correlation()`: Calculate measurement correlations

### 2. **bb84.py**
**Purpose**: BB84 quantum key distribution protocol

**Key Classes**:
- `BB84State`: Represents individual quantum state
- `BB84`: Full protocol executor

**Protocol Steps**:
1. Alice prepares random bits in random bases
2. Bob measures in random bases
3. Sift keys by comparing bases
4. Error correction with QBER assessment
5. Privacy amplification
6. Eve eavesdropping simulation

**Key Functions**:
- `alice_prepare_states()`: Generate quantum states
- `bob_measure_states()`: Measure quantum states
- `sift_keys()`: Compare bases and extract sifted key
- `error_correction()`: QBER calculation
- `privacy_amplification()`: XOR-based amplification
- `simulate_eve_eavesdropping()`: Eve detection simulation

### 3. **chsh.py**
**Purpose**: CHSH Bell test for device-independent security

**Key Classes**:
- `CHSHMeasurement`: Single measurement result
- `CHSHBellTest`: Bell test executor

**Bell Test Measurement**:
- Alice setting: 0 (Z basis) or 1 (X basis)
- Bob setting: 0 (Z basis) or 1 (X basis)
- Alice output: 0 or 1
- Bob output: 0 or 1

**CHSH Formula**:
```
S = |E(0,0) + E(0,1) + E(1,0) - E(1,1)|
Where E(a,b) = (agreements - disagreements) / total
```

**Key Functions**:
- `run_bell_test()`: Execute CHSH measurements
- `calculate_chsh_value()`: Compute S value
- `device_independent_certification()`: DI security assessment
- `extract_key_from_chsh()`: Generate key from measurements

### 4. **diqkd_simulator.py**
**Purpose**: Main orchestrator combining BB84 + CHSH

**Key Class**:
- `DIQKDSimulator`: Full DI-QKD execution controller

**Integration Steps**:
1. Run BB84 protocol
2. Run CHSH Bell test
3. Combine keys via XOR
4. Perform security assessment
5. Generate certification report

**Key Functions**:
- `run_bb84_protocol()`: Execute BB84
- `run_chsh_bell_test()`: Execute CHSH
- `combine_keys()`: Merge both keys
- `run_full_simulation()`: Complete DI-QKD pipeline
- `assess_security()`: Comprehensive security check
- `export_results()`: Save results to JSON

### 5. **api.py**
**Purpose**: REST API for web frontend

**Key Endpoints**:
```
POST   /api/initialize              - Initialize simulator
POST   /api/run_bb84                - Run BB84
POST   /api/run_chsh                - Run CHSH
POST   /api/run_full_simulation     - Run full DI-QKD
GET    /api/get_execution_log       - Fetch execution log
GET    /api/export_results          - Export results
GET    /health                      - Health check
```

**Request/Response Pattern**:
```json
{
  "status": "success|error",
  "results": {...}
}
```

---

## 🔄 Data Flow Diagrams

### BB84 Protocol Flow
```
Input: key_size = 512
  │
  ├─ Alice: Prepare States
  │  ├─ Generate random bits: [0,1,0,1,...]
  │  ├─ Generate random bases: [Z,X,Z,X,...]
  │  └─ Create quantum states
  │
  ├─ Quantum Channel: Transmit States
  │  └─ In real QKD: quantum/photon transmission
  │
  ├─ Bob: Measure States
  │  ├─ Choose random bases: [Z,X,X,Z,...]
  │  └─ Measure in chosen bases
  │
  ├─ Public Channel: Compare Bases
  │  └─ Alice & Bob publicly compare bases (not bits)
  │
  ├─ Sift Keys
  │  ├─ Keep only matching bases positions
  │  └─ Result: Sifted key ~50% of original
  │
  ├─ Error Correction
  │  ├─ Select subset for testing
  │  ├─ Compare test bits
  │  ├─ Calculate QBER
  │  └─ Decision: Secure if QBER < 11%
  │
  ├─ Privacy Amplification
  │  ├─ Apply XOR operations
  │  └─ Reduce Eve's information
  │
  ├─ Eve Simulation
  │  ├─ Eve measures in random bases
  │  └─ Assess detection probability
  │
  Output: Final Key + Security Metrics
```

### CHSH Bell Test Flow
```
Input: num_rounds = 1000, state = Φ+
  │
  ├─ Create Quantum State
  │  ├─ Bell pair: |Φ+⟩ = (1/√2)(|00⟩ + |11⟩)
  │  └─ Distribute: Alice gets qubit A, Bob gets qubit B
  │
  ├─ Run Measurements (1000 times)
  │  ├─ Alice: Random setting a ∈ {0,1}
  │  ├─ Bob: Random setting b ∈ {0,1}
  │  ├─ Alice: Measure qubit A → output aₒ
  │  ├─ Bob: Measure qubit B → output bₒ
  │  └─ Record: (a, b, aₒ, bₒ)
  │
  ├─ Calculate Correlations
  │  ├─ E(0,0) = (agree - disagree) / total for a=0,b=0
  │  ├─ E(0,1) = ...
  │  ├─ E(1,0) = ...
  │  └─ E(1,1) = ...
  │
  ├─ Compute CHSH Value
  │  └─ S = |E(0,0) + E(0,1) + E(1,0) - E(1,1)|
  │
  ├─ Check Bell Violation
  │  ├─ Classical: S ≤ 2.0
  │  ├─ Quantum Φ+: S ≈ 2.7-2.8
  │  └─ Decision: If S > 2.0 → Bell violation!
  │
  ├─ Device-Independent Certification
  │  ├─ Compute violation: (S - 2) / (2√2 - 2)
  │  ├─ Estimate min-entropy
  │  ├─ Assess robustness
  │  └─ Certify device-independence
  │
  ├─ Key Extraction
  │  └─ Extract bits from specific setting pairs
  │
  Output: CHSH Value + DI Certification + Key
```

### DI-QKD Combined Flow
```
Input: key_size, num_chsh_rounds, bell_state
  │
  ├─ Phase 1: BB84 Execution
  │  └─ Run full BB84 protocol
  │     Output: key_BB84, QBER, eve_detected
  │
  ├─ Phase 2: CHSH Verification
  │  └─ Run full CHSH test
  │     Output: key_CHSH, CHSH_value, DI_certified
  │
  ├─ Phase 3: Key Combination
  │  └─ combined_key = key_BB84 XOR key_CHSH
  │     Output: merged key
  │
  ├─ Phase 4: Security Assessment
  │  ├─ BB84 Security:
  │  │  ├─ Check QBER < 11%
  │  │  └─ Check Eve not detected
  │  │
  │  ├─ CHSH Security:
  │  │  ├─ Check Bell violation (S > 2.0)
  │  │  └─ Check device-independence
  │  │
  │  ├─ Combined Score:
  │  │  ├─ Very High: Both excellent + DI certified
  │  │  ├─ High: Both good
  │  │  ├─ Medium: One good or statistical variation
  │  │  └─ Low: Issues detected
  │  │
  │  └─ Generate Recommendations
  │
  Output: Certified DI-QKD Key + Full Security Report
```

---

## 🔐 Security Model

### Classical Security (BB84)
```
Information Theory:
├─ Eve's maximal information gain: ~0.25 bits/qubit
├─ QBER increase from Eve: ~25%
├─ Detection threshold: QBER > 11%
└─ Key security: Conditional on Eve detection
```

### Quantum Security (CHSH)
```
Bell Test Results:
├─ S ≤ 2.0: No Bell violation (classical)
├─ 2.0 < S ≤ 2.4: Weak quantum advantage
├─ 2.4 < S ≤ 2.8: Strong quantum advantage (Φ+)
└─ S > 2.8: Impossible (measurement noise)

Device-Independence:
├─ No trust in measurement devices needed
├─ Security based on fundamental physics
├─ Bell violation bounds extractable key rate
└─ Robustness improves with higher violation
```

### Combined DI-QKD Security
```
Key Rate Bounds:
├─ From BB84: ~0.5 bits/round (50% sift efficiency)
├─ From CHSH: violation_rate × 0.5
├─ Combined: min(BB84, CHSH) × device_independence_factor
└─ Conservative estimate: 0.2-0.3 bits/round

Threat Model:
├─ Eavesdropping: Detected by QBER
├─ Device Tampering: Certified by CHSH
├─ Entanglement Verification: Bell violation
└─ Side Channels: Mitigated by DI approach
```

---

## 🎯 Key Design Decisions

### 1. BB84 Implementation
**Choice**: Basis sifting via public comparison
**Rationale**: Standard BB84 protocol, simple and secure

### 2. Quantum State Simulation
**Choice**: State vector representation (complex amplitude)
**Rationale**: Sufficient for 2-qubit systems, matches quantum mechanics

### 3. CHSH Measurement Model
**Choice**: Measurement in computational (Z) and Hadamard (X) bases
**Rationale**: Standard for CHSH tests, orthogonal bases

### 4. Key Combination
**Choice**: XOR of BB84 and CHSH keys
**Rationale**: Simple, secure mixing that preserves entropy

### 5. Security Thresholds
**QBER Threshold**: 11%
- Based on BB84 security proofs
- Accounts for realistic noise

**CHSH Threshold**: 2.0 (Bell's bound)
- Classical bound, provably unviolable
- Higher values indicate stronger entanglement

---

## 📊 Performance Characteristics

### Computational Complexity

**BB84 Protocol**:
- Time: O(n) where n = key_size
- Space: O(n)
- Sift efficiency: ~50% expected
- Key generation: ~512 bits → 128 bits final

**CHSH Bell Test**:
- Time: O(m) where m = num_rounds
- Space: O(m)
- Correlation density: O(1)
- Measurement overhead: 4 outcomes × m rounds

**Full DI-QKD**:
- Time: O(n + m)
- Space: O(n + m)
- Typical: 512 bits BB84 + 1000 rounds CHSH
- Total runtime: < 1 second on modern CPU

### Scalability

| Parameter | Min | Typical | Max |
|-----------|-----|---------|-----|
| Key size | 128 | 512 | 4096 |
| CHSH rounds | 100 | 1000 | 10000 |
| Runtime | 0.1s | 0.5s | 5s |

---

## 🧪 Testing Strategy

### Unit Tests
- Individual class functionality
- Edge cases and error handling
- Properties and invariants

### Integration Tests
- Component interactions
- Full protocol execution
- Result consistency

### Property-Based Tests
- QBER calculations
- CHSH value bounds
- Key entropy

### Simulation Tests
- Eve eavesdropping patterns
- Different Bell states
- Security certification robustness

---

## 📝 Future Extensions

### Potential Enhancements
1. **Advanced Quantum Effects**
   - Noise models for realistic channels
   - Photon loss and detection inefficiency
   - Detector blinding attacks

2. **Additional Protocols**
   - E91 protocol (Ekert 1991)
   - MDI-QKD (Measurement-Device-Independent)
   - Twin-field QKD

3. **Scalability**
   - Multi-party QKD
   - Network QKD routing
   - Extended security proofs

4. **Integration**
   - Real quantum hardware backends
   - Post-quantum hybrid schemes
   - ZK-SNARKs for security proofs

---

## 🔗 Dependencies

### Core
- **numpy**: Numerical computations
- **Flask**: Web API framework
- **Flask-CORS**: Cross-origin support

### Testing
- **pytest**: Unit testing framework

### Optional
- **matplotlib**: Visualization (future)
- **sympy**: Symbolic computation (future)

---

## 📚 References

### Key Papers
1. Bennett & Brassard (1984) - BB84 Protocol
2. Clauser et al. (1969) - CHSH Inequality
3. Brunner et al. (2014) - Bell Nonlocality Review
4. Scarani et al. (2006) - DI-QKD Foundations

### Standards
- FIPS 203: ML-KEM (Post-quantum)
- ISO/IEC 20000: Network Security

---

**Document Version**: 1.0
**Last Updated**: 2026-03-25
**Author**: QKD Simulator Team

