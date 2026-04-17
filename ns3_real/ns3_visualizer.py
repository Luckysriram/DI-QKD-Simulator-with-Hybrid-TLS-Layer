"""
ns3_visualizer.py
=================
Visualization for Real NS-3 simulation results.

Generates publication-quality plots from the CSV/JSON output
produced by the real NS-3 C++ simulation (via NS3Bridge).

Plots:
  - Key rate vs distance (log scale)
  - QBER vs distance with security threshold
  - Throughput vs distance
  - Delay vs distance
  - Eve detection: QBER vs intercept rate
  - TLS handshake breakdown by distance
  - Packet loss rate comparison
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    from matplotlib.gridspec import GridSpec
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# -- Style --------------------------------------------------------------------─

_COLORS = {
    "blue":   "#4A90D9",
    "green":  "#27AE60",
    "red":    "#E74C3C",
    "orange": "#E67E22",
    "purple": "#8E44AD",
    "teal":   "#16A085",
    "gray":   "#7F8C8D",
}

_QBER_THRESHOLD = 0.11  # BB84 security threshold


def _setup_style():
    plt.rcParams.update({
        "figure.facecolor":  "#0D1117",
        "axes.facecolor":    "#161B22",
        "axes.edgecolor":    "#30363D",
        "axes.labelcolor":   "#C9D1D9",
        "axes.grid":         True,
        "grid.color":        "#21262D",
        "grid.linewidth":    0.8,
        "xtick.color":       "#C9D1D9",
        "ytick.color":       "#C9D1D9",
        "text.color":        "#C9D1D9",
        "legend.facecolor":  "#161B22",
        "legend.edgecolor":  "#30363D",
        "font.family":       "DejaVu Sans",
        "font.size":         11,
        "axes.titlesize":    13,
        "axes.titleweight":  "bold",
        "figure.dpi":        120,
    })


def _save(fig, path: str):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  [Plot] Saved: {path}")


# -- Individual plot functions ------------------------------------------------─

def plot_key_rate_vs_distance(
    distances: List[float],
    key_rates: List[float],
    output_path: str = "simulation_results/ns3_real/key_rate_vs_distance.png",
    title: str = "Secure Key Rate vs Distance (Real NS-3)",
):
    if not HAS_MATPLOTLIB:
        print("[Plot] matplotlib not installed - skipping")
        return

    _setup_style()
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.semilogy(distances, key_rates, color=_COLORS["blue"],
                linewidth=2.5, marker="o", markersize=7, label="Key Rate (bits/pulse)")

    # Mark the practical range limit (~130 km for standard APDs)
    ax.axvline(x=130, color=_COLORS["red"], linestyle="--", linewidth=1.5,
               label="~130 km practical limit")
    ax.axhline(y=1e-6, color=_COLORS["orange"], linestyle=":", linewidth=1.2,
               label="1e-6 key rate floor")

    ax.set_xlabel("Distance (km)")
    ax.set_ylabel("Secure Key Rate (bits/pulse)")
    ax.set_title(title)
    ax.legend()
    ax.set_xlim(left=0)

    # Annotate max distance with non-zero key rate
    max_idx = max((i for i, kr in enumerate(key_rates) if kr > 0), default=None)
    if max_idx is not None:
        ax.annotate(
            f"Max: {distances[max_idx]} km",
            xy=(distances[max_idx], key_rates[max_idx]),
            xytext=(distances[max_idx] - 20, key_rates[max_idx] * 10),
            arrowprops=dict(arrowstyle="->", color=_COLORS["teal"]),
            color=_COLORS["teal"],
        )

    _save(fig, output_path)


def plot_qber_vs_distance(
    distances: List[float],
    qbers: List[float],
    output_path: str = "simulation_results/ns3_real/qber_vs_distance.png",
    title: str = "QBER vs Distance (Real NS-3)",
):
    if not HAS_MATPLOTLIB:
        return

    _setup_style()
    fig, ax = plt.subplots(figsize=(10, 6))

    secure = [q < _QBER_THRESHOLD for q in qbers]
    sec_d  = [d for d, s in zip(distances, secure) if s]
    sec_q  = [q for q, s in zip(qbers, secure) if s]
    ins_d  = [d for d, s in zip(distances, secure) if not s]
    ins_q  = [q for q, s in zip(qbers, secure) if not s]

    ax.plot(distances, qbers, color=_COLORS["blue"], linewidth=2.5,
            zorder=2, label="QBER")
    ax.scatter(sec_d, sec_q, color=_COLORS["green"],  s=80, zorder=3, label="Secure")
    ax.scatter(ins_d, ins_q, color=_COLORS["red"],    s=80, zorder=3, label="Insecure")

    ax.axhline(y=_QBER_THRESHOLD, color=_COLORS["red"], linestyle="--", linewidth=2,
               label=f"Security threshold ({_QBER_THRESHOLD:.0%})")

    ax.fill_between(distances, 0, [_QBER_THRESHOLD] * len(distances),
                    alpha=0.10, color=_COLORS["green"])
    ax.fill_between(distances, [_QBER_THRESHOLD] * len(distances),
                    max(qbers) * 1.1 if qbers else 0.5,
                    alpha=0.06, color=_COLORS["red"])

    ax.set_xlabel("Distance (km)")
    ax.set_ylabel("QBER")
    ax.set_title(title)
    ax.legend()
    ax.set_xlim(left=0)
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1))

    _save(fig, output_path)


def plot_throughput_vs_distance(
    distances: List[float],
    throughputs: List[float],
    output_path: str = "simulation_results/ns3_real/throughput_vs_distance.png",
    title: str = "TCP Throughput vs Distance (Real NS-3 FlowMonitor)",
):
    if not HAS_MATPLOTLIB:
        return

    _setup_style()
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(distances, throughputs, color=_COLORS["teal"],
            linewidth=2.5, marker="s", markersize=7)
    ax.fill_between(distances, throughputs, alpha=0.15, color=_COLORS["teal"])

    ax.set_xlabel("Distance (km)")
    ax.set_ylabel("Throughput (Mbps)")
    ax.set_title(title)
    ax.set_xlim(left=0)

    _save(fig, output_path)


def plot_delay_vs_distance(
    distances: List[float],
    delays: List[float],
    output_path: str = "simulation_results/ns3_real/delay_vs_distance.png",
    title: str = "Propagation Delay vs Distance (Real NS-3 FlowMonitor)",
):
    if not HAS_MATPLOTLIB:
        return

    _setup_style()
    fig, ax = plt.subplots(figsize=(10, 6))

    # Theoretical fiber delay (5 µs/km = 0.005 ms/km)
    theoretical = [d * 0.005 for d in distances]

    ax.plot(distances, delays,       color=_COLORS["blue"],  linewidth=2.5,
            marker="o", markersize=6, label="NS-3 Measured")
    ax.plot(distances, theoretical,  color=_COLORS["gray"],  linewidth=1.5,
            linestyle="--", label="Theoretical (5 µs/km)")

    ax.set_xlabel("Distance (km)")
    ax.set_ylabel("Delay (ms)")
    ax.set_title(title)
    ax.legend()
    ax.set_xlim(left=0)

    _save(fig, output_path)


def plot_eve_detection(
    intercept_rates: List[float],
    qbers: List[float],
    is_detected: List[bool],
    output_path: str = "simulation_results/ns3_real/eve_detection.png",
    title: str = "Eavesdropper Detection via QBER (Real NS-3)",
):
    if not HAS_MATPLOTLIB:
        return

    _setup_style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Left: QBER vs intercept rate
    rates_pct = [r * 100 for r in intercept_rates]
    ax1.plot(rates_pct, qbers, color=_COLORS["purple"],
             linewidth=2.5, marker="D", markersize=8)
    ax1.axhline(y=_QBER_THRESHOLD, color=_COLORS["red"], linestyle="--", linewidth=2,
                label=f"Detection threshold ({_QBER_THRESHOLD:.0%} QBER)")

    for rate_pct, q, det in zip(rates_pct, qbers, is_detected):
        color = _COLORS["red"] if det else _COLORS["green"]
        ax1.scatter(rate_pct, q, color=color, s=120, zorder=5)

    ax1.set_xlabel("Eve Intercept Rate (%)")
    ax1.set_ylabel("QBER")
    ax1.set_title("QBER vs Eve Intercept Rate")
    ax1.legend()
    ax1.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1))

    # Right: Detection probability
    det_vals = [1 if d else 0 for d in is_detected]
    colors   = [_COLORS["red"] if d else _COLORS["green"] for d in is_detected]
    bars = ax2.bar(rates_pct, det_vals, color=colors, width=6, edgecolor="#30363D")

    for bar, det in zip(bars, is_detected):
        label = "DETECTED" if det else "Secure"
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                 label, ha="center", va="bottom", fontsize=9,
                 color=_COLORS["red"] if det else _COLORS["green"])

    ax2.set_xlabel("Eve Intercept Rate (%)")
    ax2.set_ylabel("Eve Detected")
    ax2.set_title("Eve Detection Result")
    ax2.set_ylim(0, 1.4)
    ax2.set_yticks([0, 1])
    ax2.set_yticklabels(["Not Detected", "DETECTED"])

    fig.suptitle(title, fontsize=14, fontweight="bold")
    fig.tight_layout()
    _save(fig, output_path)


def plot_tls_handshake_breakdown(
    results: List[Dict[str, Any]],
    output_path: str = "simulation_results/ns3_real/tls_handshake.png",
    title: str = "TLS Handshake Timing (Real NS-3)",
):
    if not HAS_MATPLOTLIB:
        return

    _setup_style()
    fig, ax = plt.subplots(figsize=(10, 6))

    distances  = [r.get("distance_km", 0) for r in results]
    handshakes = [r.get("tls_handshake_ms", 0) for r in results]
    transfers  = [r.get("tls_data_transfer_ms", 0) for r in results]

    x = range(len(distances))
    width = 0.35

    ax.bar([i - width/2 for i in x], handshakes, width, label="Handshake", color=_COLORS["blue"])
    ax.bar([i + width/2 for i in x], transfers,  width, label="Data Transfer", color=_COLORS["teal"])

    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{int(d)} km" for d in distances])
    ax.set_xlabel("Distance")
    ax.set_ylabel("Time (ms)")
    ax.set_title(title)
    ax.legend()

    _save(fig, output_path)


def plot_full_dashboard(
    all_results: Dict[str, List[Dict[str, Any]]],
    output_path: str = "simulation_results/ns3_real/dashboard.png",
):
    """Generate a single dashboard figure with all key metrics."""
    if not HAS_MATPLOTLIB:
        print("[Plot] matplotlib not installed - skipping dashboard")
        return

    _setup_style()
    fig = plt.figure(figsize=(20, 14), facecolor="#0D1117")
    gs  = GridSpec(3, 3, figure=fig, hspace=0.45, wspace=0.35)

    # -- Panel 1: Key Rate vs Distance ----------------------------------------
    ax1 = fig.add_subplot(gs[0, :2])
    sweep = all_results.get("distance_sweep", [])
    if sweep:
        distances  = [r["distance_km"] for r in sweep]
        key_rates  = [r["key_rate"] for r in sweep]
        nonzero    = [(d, k) for d, k in zip(distances, key_rates) if k > 0]
        if nonzero:
            d_nz, k_nz = zip(*nonzero)
            ax1.semilogy(d_nz, k_nz, color=_COLORS["blue"], linewidth=2.5,
                         marker="o", markersize=6)
    ax1.axvline(x=130, color=_COLORS["red"], linestyle="--", linewidth=1.5, alpha=0.7)
    ax1.set_title("Key Rate vs Distance")
    ax1.set_xlabel("Distance (km)")
    ax1.set_ylabel("Key Rate (bits/pulse)")

    # -- Panel 2: QBER vs Distance --------------------------------------------
    ax2 = fig.add_subplot(gs[0, 2])
    if sweep:
        distances = [r["distance_km"] for r in sweep]
        qbers     = [r["qber"] for r in sweep]
        ax2.plot(distances, qbers, color=_COLORS["purple"], linewidth=2.5, marker="o", markersize=5)
        ax2.axhline(y=_QBER_THRESHOLD, color=_COLORS["red"], linestyle="--", linewidth=1.5)
    ax2.set_title("QBER vs Distance")
    ax2.set_xlabel("Distance (km)")
    ax2.set_ylabel("QBER")
    ax2.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1))

    # -- Panel 3: Throughput --------------------------------------------------
    ax3 = fig.add_subplot(gs[1, 0])
    if sweep:
        distances   = [r["distance_km"] for r in sweep]
        throughputs = [r["throughput_mbps"] for r in sweep]
        ax3.plot(distances, throughputs, color=_COLORS["teal"], linewidth=2.5, marker="s", markersize=5)
        ax3.fill_between(distances, throughputs, alpha=0.12, color=_COLORS["teal"])
    ax3.set_title("NS-3 Throughput")
    ax3.set_xlabel("Distance (km)")
    ax3.set_ylabel("Throughput (Mbps)")

    # -- Panel 4: Delay ------------------------------------------------------
    ax4 = fig.add_subplot(gs[1, 1])
    if sweep:
        distances = [r["distance_km"] for r in sweep]
        delays    = [r["avg_delay_ms"] for r in sweep]
        ax4.plot(distances, delays, color=_COLORS["orange"], linewidth=2.5, marker="^", markersize=5)
    ax4.set_title("NS-3 Propagation Delay")
    ax4.set_xlabel("Distance (km)")
    ax4.set_ylabel("Delay (ms)")

    # -- Panel 5: Eve Detection ----------------------------------------------─
    ax5 = fig.add_subplot(gs[1, 2])
    eve_results = all_results.get("eve_attack", [])
    if eve_results:
        rates = [r.get("intercept_rate", r.get("eve_intercept_rate", 0)) for r in eve_results]
        qbers = [r["qber"] for r in eve_results]
        ax5.plot([r * 100 for r in rates], qbers, color=_COLORS["red"],
                 linewidth=2.5, marker="D", markersize=6)
        ax5.axhline(y=_QBER_THRESHOLD, color=_COLORS["orange"], linestyle="--", linewidth=1.5)
    ax5.set_title("Eve Attack: QBER Rise")
    ax5.set_xlabel("Eve Intercept Rate (%)")
    ax5.set_ylabel("QBER")
    ax5.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1))

    # -- Panel 6: TLS Handshake ----------------------------------------------─
    ax6 = fig.add_subplot(gs[2, 0])
    tls_results = all_results.get("tls_handshake", [])
    if tls_results:
        dist_labels = [f"{int(r['distance_km'])}km" for r in tls_results]
        hs_times    = [r.get("tls_handshake_ms", 0) for r in tls_results]
        dt_times    = [r.get("tls_data_transfer_ms", 0) for r in tls_results]
        x = range(len(dist_labels))
        ax6.bar([i - 0.2 for i in x], hs_times, 0.4, label="Handshake", color=_COLORS["blue"])
        ax6.bar([i + 0.2 for i in x], dt_times,  0.4, label="Data Tx",   color=_COLORS["teal"])
        ax6.set_xticks(list(x))
        ax6.set_xticklabels(dist_labels)
        ax6.legend(fontsize=8)
    ax6.set_title("TLS Timing")
    ax6.set_ylabel("Time (ms)")

    # -- Panel 7: Packet Loss ------------------------------------------------─
    ax7 = fig.add_subplot(gs[2, 1])
    if sweep:
        distances   = [r["distance_km"] for r in sweep]
        loss_rates  = [r.get("packet_loss_rate", 0) * 100 for r in sweep]
        ax7.plot(distances, loss_rates, color=_COLORS["red"], linewidth=2.5,
                 marker="o", markersize=5)
    ax7.set_title("Packet Loss Rate")
    ax7.set_xlabel("Distance (km)")
    ax7.set_ylabel("Loss Rate (%)")

    # -- Panel 8: Security Status --------------------------------------------─
    ax8 = fig.add_subplot(gs[2, 2])
    if sweep:
        secure_count   = sum(1 for r in sweep if r.get("is_secure", False))
        insecure_count = len(sweep) - secure_count
        ax8.pie(
            [secure_count, insecure_count],
            labels=["Secure", "Insecure"],
            colors=[_COLORS["green"], _COLORS["red"]],
            autopct="%1.0f%%",
            startangle=90,
            textprops={"color": "#C9D1D9"},
        )
    ax8.set_title("Security Status (Sweep)")

    fig.suptitle(
        "Real NS-3 QKD + TLS Simulation Dashboard",
        fontsize=16, fontweight="bold", color="#C9D1D9", y=1.01,
    )

    _save(fig, output_path)
    print(f"\n  [Plot] Full dashboard saved: {output_path}")


# -- Convenience: generate all plots from a JSON results file ----------------─

def generate_all_plots(
    json_path: str,
    output_dir: str = "simulation_results/ns3_real",
):
    """Load all_results.json produced by NS3Bridge.run_all_scenarios() and plot everything."""
    with open(json_path) as f:
        all_results = json.load(f)

    os.makedirs(output_dir, exist_ok=True)

    sweep = all_results.get("distance_sweep", [])
    if sweep:
        distances  = [r["distance_km"] for r in sweep]
        key_rates  = [r["key_rate"]     for r in sweep]
        qbers      = [r["qber"]         for r in sweep]
        throughputs = [r["throughput_mbps"] for r in sweep]
        delays     = [r["avg_delay_ms"] for r in sweep]

        plot_key_rate_vs_distance(distances, key_rates,
            output_path=f"{output_dir}/key_rate_vs_distance.png")
        plot_qber_vs_distance(distances, qbers,
            output_path=f"{output_dir}/qber_vs_distance.png")
        plot_throughput_vs_distance(distances, throughputs,
            output_path=f"{output_dir}/throughput_vs_distance.png")
        plot_delay_vs_distance(distances, delays,
            output_path=f"{output_dir}/delay_vs_distance.png")

    eve = all_results.get("eve_attack", [])
    if eve:
        rates   = [r.get("intercept_rate", r.get("eve_intercept_rate", 0)) for r in eve]
        qbers_e = [r["qber"] for r in eve]
        det     = [not r.get("is_secure", True) for r in eve]
        plot_eve_detection(rates, qbers_e, det,
            output_path=f"{output_dir}/eve_detection.png")

    tls = all_results.get("tls_handshake", [])
    if tls:
        plot_tls_handshake_breakdown(tls,
            output_path=f"{output_dir}/tls_handshake.png")

    plot_full_dashboard(all_results,
        output_path=f"{output_dir}/dashboard.png")

    print(f"\n[Visualizer] All plots written to: {output_dir}/")
