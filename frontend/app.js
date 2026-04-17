// DI-QKD Simulator Frontend Application
const API_BASE = 'http://localhost:5000/api';

let currentResults = null;

// Initialize simulator
async function initializeSimulator() {
    const keySize = parseInt(document.getElementById('key-size').value);
    const chshRounds = parseInt(document.getElementById('chsh-rounds').value);

    try {
        showLoading(true);
        const response = await fetch(`${API_BASE}/initialize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                key_size: keySize,
                chsh_rounds: chshRounds
            })
        });

        const data = await response.json();
        if (data.status === 'success') {
            addLog('Simulator initialized successfully');
            addLog(`Key size: ${keySize} bits, CHSH rounds: ${chshRounds}`);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to initialize simulator: ' + error.message);
    } finally {
        showLoading(false);
    }
}

// Run BB84 protocol
async function runBB84() {
    try {
        showLoading(true);
        addLog('Starting BB84 protocol...');

        const response = await fetch(`${API_BASE}/run_bb84`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();
        if (data.status === 'success') {
            updateBB84Results(data.results);
            addLog('BB84 protocol completed');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to run BB84: ' + error.message);
    } finally {
        showLoading(false);
    }
}

// Run CHSH Bell test
async function runCHSH() {
    try {
        showLoading(true);
        const stateType = document.getElementById('bell-state').value;
        addLog(`Starting CHSH Bell test with state: ${stateType}`);

        const response = await fetch(`${API_BASE}/run_chsh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ state_type: stateType })
        });

        const data = await response.json();
        if (data.status === 'success') {
            updateCHSHResults(data.results);
            updateCorrelations(data.results.correlations);
            addLog('CHSH Bell test completed');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to run CHSH: ' + error.message);
    } finally {
        showLoading(false);
    }
}

// Run full simulation
async function runFullSimulation() {
    try {
        showLoading(true);
        const stateType = document.getElementById('bell-state').value;
        addLog('Starting full DI-QKD simulation...');

        const response = await fetch(`${API_BASE}/run_full_simulation`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chsh_state: stateType })
        });

        const data = await response.json();
        if (data.status === 'success') {
            currentResults = data.results;
            updateBB84Results(data.results.bb84_results);
            updateCHSHResults(data.results.chsh_results);
            updateSecurityCertification(data.results.security_certification);
            addLog('Full DI-QKD simulation completed');
            
            // Fetch execution log
            fetchExecutionLog();
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to run simulation: ' + error.message);
    } finally {
        showLoading(false);
    }
}

// Fetch execution log
async function fetchExecutionLog() {
    try {
        const response = await fetch(`${API_BASE}/get_execution_log`);
        const data = await response.json();
        if (data.status === 'success') {
            updateExecutionLog(data.log);
        }
    } catch (error) {
        console.error('Error fetching log:', error);
    }
}

// Update BB84 results in UI
function updateBB84Results(results) {
    document.getElementById('bb84-initial').textContent = results.initial_bits;
    document.getElementById('bb84-sifted').textContent = results.sifted_key_length;
    document.getElementById('bb84-final').textContent = results.final_key_length;
    document.getElementById('bb84-qber').innerHTML = 
        `<span class="${results.qber < 0.11 ? 'status-success' : 'status-danger'}">${(results.qber * 100).toFixed(4)}%</span>`;
    document.getElementById('bb84-eve').innerHTML = 
        `<span class="${results.eve_detected ? 'status-danger' : 'status-success'}">${results.eve_detected ? 'YES' : 'NO'}</span>`;
    document.getElementById('bb84-efficiency').textContent = 
        `${(results.sifted_key_length / results.initial_bits * 100).toFixed(2)}%`;
}

// Update CHSH results in UI
function updateCHSHResults(results) {
    document.getElementById('chsh-value').innerHTML = 
        `<span class="${results.violates_bell ? 'status-success' : 'status-warning'}">${results.chsh_value.toFixed(4)}</span>`;
    document.getElementById('chsh-violation').innerHTML = 
        `<span class="${results.violates_bell ? 'status-success' : 'status-warning'}">${results.violates_bell ? 'YES' : 'NO'}</span>`;
    document.getElementById('chsh-di').innerHTML = 
        `<span class="${results.device_independent ? 'status-success' : 'status-warning'}">${results.device_independent ? 'YES' : 'NO'}</span>`;
    document.getElementById('chsh-robustness').textContent = results.security_robustness;
}

// Update correlations
function updateCorrelations(correlations) {
    let html = '';
    for (const [key, value] of Object.entries(correlations)) {
        html += `
            <div class="result-item">
                <span class="result-label">${key}:</span>
                <span class="result-value">${value.toFixed(6)}</span>
            </div>
        `;
    }
    document.getElementById('correlations-content').innerHTML = html;
}

// Update security certification
function updateSecurityCertification(cert) {
    const levelClass = cert.overall_security_level.includes('Very High') ? 'status-success' 
                     : cert.overall_security_level.includes('High') ? 'status-success'
                     : 'status-warning';
    
    document.getElementById('security-level').innerHTML = 
        `<span class="${levelClass}">${cert.overall_security_level}</span>`;
    document.getElementById('security-di').innerHTML = 
        `<span class="${cert.device_independent_certified ? 'status-success' : 'status-warning'}">${cert.device_independent_certified ? 'YES' : 'NO'}</span>`;
    document.getElementById('security-key-length').textContent = cert.key_size;
    document.getElementById('security-quantum').innerHTML = 
        `<span class="${cert.quantum_advantage ? 'status-success' : 'status-warning'}">${cert.quantum_advantage ? 'YES' : 'NO'}</span>`;
    
    // Display recommendations
    let recsHtml = '<strong>Recommendations:</strong><ul>';
    cert.recommendations.forEach(rec => {
        recsHtml += `<li>${rec}</li>`;
    });
    recsHtml += '</ul>';
    document.getElementById('recommendations').innerHTML = recsHtml;
}

// Update execution log
function updateExecutionLog(log) {
    let html = '';
    log.forEach(entry => {
        html += `<div class="log-entry">${escapeHtml(entry)}</div>`;
    });
    document.getElementById('execution-log').innerHTML = html;
    // Auto-scroll to bottom
    document.getElementById('execution-log').scrollTop = document.getElementById('execution-log').scrollHeight;
}

// Add log entry
function addLog(message) {
    const logContainer = document.getElementById('execution-log');
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    const timestamp = new Date().toLocaleTimeString();
    entry.textContent = `[${timestamp}] ${message}`;
    logContainer.appendChild(entry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

// Reset simulator
async function resetSimulator() {
    try {
        const response = await fetch(`${API_BASE}/reset`, {
            method: 'POST'
        });
        const data = await response.json();
        if (data.status === 'success') {
            // Clear display
            document.getElementById('bb84-initial').textContent = '-';
            document.getElementById('bb84-sifted').textContent = '-';
            document.getElementById('bb84-final').textContent = '-';
            document.getElementById('bb84-qber').textContent = '-';
            document.getElementById('bb84-eve').textContent = '-';
            document.getElementById('bb84-efficiency').textContent = '-';
            document.getElementById('chsh-value').textContent = '-';
            document.getElementById('chsh-violation').textContent = '-';
            document.getElementById('chsh-di').textContent = '-';
            document.getElementById('chsh-robustness').textContent = '-';
            document.getElementById('security-level').textContent = '-';
            document.getElementById('security-di').textContent = '-';
            document.getElementById('security-key-length').textContent = '-';
            document.getElementById('security-quantum').textContent = '-';
            document.getElementById('recommendations').innerHTML = '';
            document.getElementById('execution-log').innerHTML = '<div class="log-entry">Ready for simulation...</div>';
            
            addLog('Simulator reset');
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

// Export results
async function exportResults() {
    if (!currentResults) {
        alert('No results to export. Run a simulation first.');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/export_results`);
        const data = await response.json();
        if (data.status === 'success') {
            alert(`Results exported to: ${data.filename}`);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to export results: ' + error.message);
    }
}

// Show/hide loading spinner
function showLoading(show) {
    document.getElementById('loading').style.display = show ? 'block' : 'none';
}

// Switch tabs
function switchTab(tabName) {
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(el => {
        el.classList.remove('active');
    });
    
    // Remove active class from all tabs
    document.querySelectorAll('.tab').forEach(el => {
        el.classList.remove('active');
    });
    
    // Show selected tab content
    document.getElementById(tabName).classList.add('active');
    
    // Add active class to clicked tab
    event.target.classList.add('active');
}

// Utility: Escape HTML
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// Check API health on load
window.addEventListener('load', async () => {
    try {
        const response = await fetch(`${API_BASE}/../health`);
        if (!response.ok) {
            console.warn('API health check failed - backend may not be running');
        }
    } catch (error) {
        console.warn('Cannot connect to API - make sure backend is running on port 5000');
    }
});
