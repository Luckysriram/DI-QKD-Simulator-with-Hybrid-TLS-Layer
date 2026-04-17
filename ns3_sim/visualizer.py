"""
Visualization — Matplotlib plots for QKD simulation results

Generates publication-quality plots for:
- Key rate vs fiber distance
- QBER vs channel noise
- TLS handshake timing breakdown
- Throughput analysis
"""

import os
from typing import Dict, Any, List, Optional

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from ns3_sim.metrics import MetricsCollector

# Plot styling
COLORS = {
    'primary': '#6366f1',     # Indigo
    'secondary': '#ec4899',   # Pink
    'success': '#22c55e',     # Green
    'warning': '#f59e0b',     # Amber
    'danger': '#ef4444',      # Red
    'info': '#3b82f6',        # Blue
    'dark': '#1e293b',        # Slate
    'grid': '#e2e8f0',        # Light gray
}

STYLE_CONFIG = {
    'figure.facecolor': '#0f172a',
    'axes.facecolor': '#1e293b',
    'text.color': '#e2e8f0',
    'axes.labelcolor': '#e2e8f0',
    'xtick.color': '#94a3b8',
    'ytick.color': '#94a3b8',
    'axes.edgecolor': '#334155',
    'grid.color': '#334155',
    'grid.alpha': 0.5,
    'font.size': 11,
    'axes.titlesize': 14,
    'axes.labelsize': 12,
}


def _apply_style():
    """Apply dark theme styling."""
    if HAS_MATPLOTLIB:
        plt.rcParams.update(STYLE_CONFIG)


def plot_key_rate_vs_distance(
    distances: List[float],
    key_rates: List[float],
    output_path: str = "key_rate_vs_distance.png",
    title: str = "QKD Key Rate vs Fiber Distance"
) -> str:
    """
    Plot key generation rate as a function of fiber distance.
    
    Returns:
        Path to saved plot
    """
    if not HAS_MATPLOTLIB:
        return ""
    
    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.semilogy(distances, key_rates, 'o-',
                color=COLORS['primary'], linewidth=2, markersize=8,
                label='Key rate (bits/pulse)')
    
    # Mark the practical limit
    ax.axhline(y=1e-6, color=COLORS['danger'], linestyle='--',
               alpha=0.7, label='Practical limit')
    
    ax.set_xlabel('Fiber Distance (km)')
    ax.set_ylabel('Key Rate (bits/pulse)')
    ax.set_title(title)
    ax.legend(facecolor='#1e293b', edgecolor='#334155')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    return output_path


def plot_qber_vs_distance(
    distances: List[float],
    qbers: List[float],
    output_path: str = "qber_vs_distance.png",
    title: str = "QBER vs Fiber Distance"
) -> str:
    """Plot QBER as a function of distance."""
    if not HAS_MATPLOTLIB:
        return ""
    
    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.plot(distances, qbers, 'o-',
            color=COLORS['secondary'], linewidth=2, markersize=8,
            label='Channel QBER')
    
    # Security threshold
    ax.axhline(y=0.11, color=COLORS['danger'], linestyle='--',
               linewidth=2, alpha=0.8, label='Security threshold (11%)')
    
    # Safe zone
    ax.fill_between(distances, 0, 0.11, alpha=0.1, color=COLORS['success'])
    ax.fill_between(distances, 0.11, max(max(qbers), 0.15), alpha=0.1, color=COLORS['danger'])
    
    ax.set_xlabel('Fiber Distance (km)')
    ax.set_ylabel('QBER')
    ax.set_title(title)
    ax.set_ylim(0, max(max(qbers) * 1.2, 0.15))
    ax.legend(facecolor='#1e293b', edgecolor='#334155')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    return output_path


def plot_tls_handshake_breakdown(
    timing: Dict[str, float],
    output_path: str = "tls_handshake.png",
    title: str = "TLS Handshake Timing Breakdown"
) -> str:
    """Plot TLS handshake timing breakdown as a horizontal bar chart."""
    if not HAS_MATPLOTLIB:
        return ""
    
    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 5))
    
    labels = list(timing.keys())
    values = list(timing.values())
    colors_list = [
        COLORS['primary'], COLORS['secondary'], COLORS['info'],
        COLORS['warning'], COLORS['success'], COLORS['danger'],
    ]
    
    bars = ax.barh(labels, values,
                   color=[colors_list[i % len(colors_list)] for i in range(len(labels))],
                   height=0.6, edgecolor='none')
    
    # Add value labels
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height()/2,
                f'{val:.2f} ms', va='center', color='#e2e8f0', fontsize=10)
    
    ax.set_xlabel('Time (ms)')
    ax.set_title(title)
    ax.invert_yaxis()
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    return output_path


def plot_eve_detection(
    intercept_rates: List[float],
    qbers: List[float],
    detected: List[bool],
    output_path: str = "eve_detection.png",
    title: str = "Eavesdropper Detection via QBER"
) -> str:
    """Plot QBER increase due to eavesdropping at different intercept rates."""
    if not HAS_MATPLOTLIB:
        return ""
    
    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 6))
    
    colors = [COLORS['danger'] if d else COLORS['success'] for d in detected]
    
    ax.bar(intercept_rates, qbers, width=0.03,
           color=colors, edgecolor='none', alpha=0.8)
    
    ax.axhline(y=0.11, color=COLORS['warning'], linestyle='--',
               linewidth=2, label='QBER threshold (11%)')
    
    ax.set_xlabel('Eve Intercept Rate')
    ax.set_ylabel('Measured QBER')
    ax.set_title(title)
    ax.legend(facecolor='#1e293b', edgecolor='#334155')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    return output_path


def plot_throughput(
    data_sizes: List[int],
    throughputs_mbps: List[float],
    output_path: str = "throughput.png",
    title: str = "Encrypted Data Throughput"
) -> str:
    """Plot throughput vs data size."""
    if not HAS_MATPLOTLIB:
        return ""
    
    _apply_style()
    fig, ax = plt.subplots(figsize=(10, 6))
    
    sizes_kb = [s / 1024 for s in data_sizes]
    
    ax.plot(sizes_kb, throughputs_mbps, 'o-',
            color=COLORS['info'], linewidth=2, markersize=8)
    
    ax.set_xlabel('Data Size (KB)')
    ax.set_ylabel('Throughput (Mbps)')
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    return output_path


def generate_report(
    metrics: MetricsCollector,
    output_dir: str = "simulation_results"
) -> Dict[str, str]:
    """
    Generate a full set of plots from collected metrics.
    
    Returns:
        dict mapping plot names to file paths
    """
    if not HAS_MATPLOTLIB:
        return {'error': 'matplotlib not available'}
    
    os.makedirs(output_dir, exist_ok=True)
    plots = {}
    
    # Key rate vs distance
    distances = metrics.get_metric_values('distance_km')
    key_rates = metrics.get_metric_values('key_rate')
    if distances and key_rates and len(distances) == len(key_rates):
        path = os.path.join(output_dir, 'key_rate_vs_distance.png')
        plots['key_rate'] = plot_key_rate_vs_distance(distances, key_rates, path)
    
    # QBER vs distance
    qbers = metrics.get_metric_values('qber')
    if distances and qbers and len(distances) == len(qbers):
        path = os.path.join(output_dir, 'qber_vs_distance.png')
        plots['qber'] = plot_qber_vs_distance(distances, qbers, path)
    
    # TLS handshake
    handshake_data = metrics.get_metric('handshake_ms')
    if handshake_data:
        timing = {p.get('phase', f'phase_{i}'): p['value']
                  for i, p in enumerate(handshake_data)}
        path = os.path.join(output_dir, 'tls_handshake.png')
        plots['handshake'] = plot_tls_handshake_breakdown(timing, path)
    
    # Export metrics data
    csv_path = os.path.join(output_dir, 'metrics.csv')
    metrics.to_csv(csv_path)
    plots['metrics_csv'] = csv_path
    
    json_path = os.path.join(output_dir, 'metrics.json')
    metrics.to_json(json_path)
    plots['metrics_json'] = json_path
    
    return plots
