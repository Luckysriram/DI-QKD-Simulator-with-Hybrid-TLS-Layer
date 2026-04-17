"""
run_real_ns3.py
===============
Main entry point for running QKD simulations on REAL NS-3.

This script is the drop-in replacement for demo_tls_ns3.py but
routes all computation through real NS-3 running in WSL.

Usage:
    python run_real_ns3.py                      # Run all scenarios
    python run_real_ns3.py --scenario fiber_10km
    python run_real_ns3.py --scenario eve_attack --intercept 0.5
    python run_real_ns3.py --scenario distance_sweep
    python run_real_ns3.py --scenario custom --distance 75 --bandwidth 500
    python run_real_ns3.py --verify-only        # Just check NS-3 setup
    python run_real_ns3.py --plots-only         # Re-plot existing results
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent))

from ns3_real.ns3_bridge import NS3Bridge
from ns3_real.ns3_visualizer import (
    generate_all_plots,
    plot_key_rate_vs_distance,
    plot_qber_vs_distance,
    plot_throughput_vs_distance,
    plot_delay_vs_distance,
    plot_eve_detection,
    plot_tls_handshake_breakdown,
    plot_full_dashboard,
    HAS_MATPLOTLIB,
)

OUTPUT_DIR = "simulation_results/ns3_real"


# -- Pretty printing ----------------------------------------------------------─

def header(title: str):
    print(f"\n{'='*62}")
    print(f"  {title}")
    print(f"{'='*62}\n")


def row(label: str, value, unit: str = ""):
    print(f"  {label:35s}: {value} {unit}")


def print_results_table(results: list, title: str = "Results"):
    print(f"\n  {title}")
    print(f"  {'-'*90}")
    print(f"  {'Scenario':<22} {'Dist':>7} {'QBER':>8} {'KeyRate':>12} {'Secure':>7}"
          f" {'Thrpt':>10} {'Delay':>9} {'Loss':>8}")
    print(f"  {'-'*90}")
    for r in results:
        print(
            f"  {str(r.get('scenario','')):<22}"
            f" {r.get('distance_km',0):>7.1f}"
            f" {r.get('qber',0):>8.4f}"
            f" {r.get('key_rate',0):>12.8f}"
            f" {'YES' if r.get('is_secure') else 'NO':>7}"
            f" {r.get('throughput_mbps',0):>9.3f}M"
            f" {r.get('avg_delay_ms',0):>8.4f}ms"
            f" {r.get('packet_loss_rate',0):>7.4f}"
        )
    print(f"  {'-'*90}")


# -- Scenario runners --------------------------------------------------------─

def run_fiber_scenarios(bridge: NS3Bridge, args) -> dict:
    """Run the three fiber distance scenarios."""
    header("Fiber Channel Scenarios (10 km / 50 km / 100 km)")

    all_fiber = {}
    for sc, dist in [("fiber_10km", 10), ("fiber_50km", 50), ("fiber_100km", 100)]:
        csv_path = f"{OUTPUT_DIR}/{sc}.csv"
        print(f"-- {sc} --")
        results = bridge.run_scenario(
            sc,
            bandwidth_mbps=args.bandwidth,
            sim_duration_s=args.duration,
            output_path=csv_path,
        )
        print_results_table(results, f"{sc} results")
        all_fiber[sc] = results
    return all_fiber


def run_satellite_scenario(bridge: NS3Bridge, args) -> dict:
    """Run LEO satellite scenario."""
    header("LEO Satellite Scenario (600 km free-space)")
    csv_path = f"{OUTPUT_DIR}/satellite_leo.csv"
    results = bridge.run_scenario(
        "satellite_leo",
        bandwidth_mbps=100.0,
        sim_duration_s=args.duration,
        output_path=csv_path,
    )
    print_results_table(results, "Satellite results")
    return {"satellite_leo": results}


def run_eve_scenario(bridge: NS3Bridge, args) -> dict:
    """Run eavesdropper detection scenario."""
    header("Eavesdropper Detection Scenario")
    csv_path = f"{OUTPUT_DIR}/eve_attack.csv"
    results = bridge.run_scenario(
        "eve_attack",
        eve_intercept_rate=args.intercept,
        sim_duration_s=args.duration,
        output_path=csv_path,
    )
    print_results_table(results, "Eve Attack results")

    # Summary table
    print(f"\n  {'Intercept':>12}  {'QBER':>8}  {'Secure':>8}  {'Eve Detected':>14}")
    print(f"  {'-'*50}")
    for r in results:
        ir = r.get("intercept_rate", r.get("eve_intercept_rate", 0))
        qber = r.get("qber", 0)
        secure = r.get("is_secure", False)
        detected = not secure
        print(
            f"  {ir:>11.0%}  {qber:>8.4f}  "
            f"{'[OK] Secure' if secure else '[!] Insecure':>11}  "
            f"{'[OK] DETECTED' if detected else 'Not detected':>15}"
        )

    return {"eve_attack": results}


def run_distance_sweep(bridge: NS3Bridge, args) -> dict:
    """Run key rate vs distance sweep."""
    header("Distance Sweep (1 – 200 km)")
    csv_path = f"{OUTPUT_DIR}/distance_sweep.csv"
    results = bridge.run_scenario(
        "distance_sweep",
        bandwidth_mbps=args.bandwidth,
        sim_duration_s=min(args.duration, 3.0),  # shorter per point
        output_path=csv_path,
    )
    print_results_table(results, "Distance Sweep results")

    if HAS_MATPLOTLIB and results:
        distances   = [r["distance_km"] for r in results]
        key_rates   = [r["key_rate"] for r in results]
        qbers       = [r["qber"] for r in results]
        throughputs = [r["throughput_mbps"] for r in results]
        delays      = [r["avg_delay_ms"] for r in results]

        plot_key_rate_vs_distance(distances, key_rates,
            output_path=f"{OUTPUT_DIR}/key_rate_vs_distance.png")
        plot_qber_vs_distance(distances, qbers,
            output_path=f"{OUTPUT_DIR}/qber_vs_distance.png")
        plot_throughput_vs_distance(distances, throughputs,
            output_path=f"{OUTPUT_DIR}/throughput_vs_distance.png")
        plot_delay_vs_distance(distances, delays,
            output_path=f"{OUTPUT_DIR}/delay_vs_distance.png")
        print(f"\n  [Plots] Saved to {OUTPUT_DIR}/")

    return {"distance_sweep": results}


def run_tls_scenario(bridge: NS3Bridge, args) -> dict:
    """Run TLS handshake timing analysis."""
    header("TLS Handshake Analysis (ECDH + ML-KEM-768 + QKD)")
    csv_path = f"{OUTPUT_DIR}/tls_handshake.csv"
    results = bridge.run_scenario(
        "tls_handshake",
        bandwidth_mbps=args.bandwidth,
        sim_duration_s=args.duration,
        output_path=csv_path,
    )

    print_results_table(results, "TLS Handshake results")
    print(f"\n  {'Distance':>10}  {'Handshake':>14}  {'Data Tx':>12}")
    print(f"  {'-'*42}")
    for r in results:
        print(
            f"  {r.get('distance_km',0):>9.0f}km"
            f"  {r.get('tls_handshake_ms',0):>12.4f}ms"
            f"  {r.get('tls_data_transfer_ms',0):>10.4f}ms"
        )

    if HAS_MATPLOTLIB and results:
        plot_tls_handshake_breakdown(results,
            output_path=f"{OUTPUT_DIR}/tls_handshake.png")

    return {"tls_handshake": results}


def run_custom_scenario(bridge: NS3Bridge, args) -> dict:
    """Run a custom single-point scenario."""
    header(f"Custom Scenario - {args.distance} km, intercept={args.intercept}")
    csv_path = f"{OUTPUT_DIR}/custom.csv"
    results = bridge.run_scenario(
        "custom",
        distance_km=args.distance,
        bandwidth_mbps=args.bandwidth,
        eve_intercept_rate=args.intercept,
        sim_duration_s=args.duration,
        output_path=csv_path,
    )
    print_results_table(results, "Custom results")
    return {"custom": results}


# -- Main ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run QKD + TLS simulation on REAL NS-3 (via WSL)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_real_ns3.py                           # All scenarios
  python run_real_ns3.py --scenario fiber_10km
  python run_real_ns3.py --scenario eve_attack --intercept 0.5
  python run_real_ns3.py --scenario distance_sweep
  python run_real_ns3.py --scenario custom --distance 75 --intercept 0.3
  python run_real_ns3.py --verify-only
  python run_real_ns3.py --plots-only
        """,
    )

    parser.add_argument(
        "--scenario",
        choices=["all", "fiber_10km", "fiber_50km", "fiber_100km",
                 "satellite_leo", "eve_attack", "distance_sweep",
                 "tls_handshake", "custom"],
        default="all",
        help="Scenario to run (default: all)",
    )
    parser.add_argument("--distance",   type=float, default=10.0,  help="Distance in km (for custom)")
    parser.add_argument("--bandwidth",  type=float, default=1000.0,help="Link bandwidth Mbps")
    parser.add_argument("--intercept",  type=float, default=0.0,   help="Eve intercept rate 0.0-1.0")
    parser.add_argument("--duration",   type=float, default=5.0,   help="Sim duration in seconds")
    parser.add_argument("--verify-only",action="store_true",        help="Only verify NS-3 setup")
    parser.add_argument("--plots-only", action="store_true",        help="Re-plot from existing JSON")
    parser.add_argument("--ns3-root",   default="/home/lenovo/ns-3-dev", help="NS-3 path in WSL")
    parser.add_argument("--no-plots",   action="store_true",        help="Skip generating plots")

    args = parser.parse_args()

    # Banner
    print("\n" + "=" * 62)
    print("  Real NS-3 QKD + TLS Simulation".center(62))
    print("  Hybrid Quantum-Resistant Communication Stack".center(62))
    print("=" * 62 + "\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    bridge = NS3Bridge(ns3_root=args.ns3_root)

    # -- Verify only ----------------------------------------------------------─
    if args.verify_only:
        ok = bridge.verify()
        sys.exit(0 if ok else 1)

    # -- Plots only ------------------------------------------------------------
    if args.plots_only:
        json_path = f"{OUTPUT_DIR}/all_results.json"
        if not os.path.exists(json_path):
            print(f"[ERROR] No results file found: {json_path}")
            print("        Run without --plots-only first to generate data.")
            sys.exit(1)
        print(f"[Plots] Re-generating plots from: {json_path}")
        generate_all_plots(json_path, OUTPUT_DIR)
        sys.exit(0)

    # -- Verify NS-3 before running --------------------------------------------
    print("Verifying NS-3 installation...\n")
    if not bridge.verify():
        print("[ERROR] NS-3 verification failed. Aborting.")
        sys.exit(1)

    # -- Build the simulation script ------------------------------------------─
    if not bridge.build():
        print("[ERROR] Build failed. Check C++ code and NS-3 installation.")
        sys.exit(1)

    # -- Run scenarios --------------------------------------------------------─
    t_start = time.time()
    all_results: dict = {}

    try:
        if args.scenario == "all":
            all_results.update(run_fiber_scenarios(bridge, args))
            all_results.update(run_satellite_scenario(bridge, args))
            all_results.update(run_eve_scenario(bridge, args))
            all_results.update(run_distance_sweep(bridge, args))
            all_results.update(run_tls_scenario(bridge, args))

        elif args.scenario in ("fiber_10km", "fiber_50km", "fiber_100km"):
            all_results.update(run_fiber_scenarios(bridge, args))

        elif args.scenario == "satellite_leo":
            all_results.update(run_satellite_scenario(bridge, args))

        elif args.scenario == "eve_attack":
            all_results.update(run_eve_scenario(bridge, args))

        elif args.scenario == "distance_sweep":
            all_results.update(run_distance_sweep(bridge, args))

        elif args.scenario == "tls_handshake":
            all_results.update(run_tls_scenario(bridge, args))

        elif args.scenario == "custom":
            all_results.update(run_custom_scenario(bridge, args))

    except KeyboardInterrupt:
        print("\n\n[Interrupted by user]")

    except Exception as e:
        print(f"\n[ERROR] Simulation failed: {e}")
        sys.exit(1)

    # -- Save combined JSON ----------------------------------------------------
    json_path = f"{OUTPUT_DIR}/all_results.json"
    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n[Output] Results JSON: {json_path}")

    # -- Generate dashboard ----------------------------------------------------
    if not args.no_plots and HAS_MATPLOTLIB and all_results:
        print("\n[Plots] Generating plots...")
        try:
            plot_full_dashboard(all_results,
                output_path=f"{OUTPUT_DIR}/dashboard.png")
        except Exception as e:
            print(f"[Plots] Dashboard error: {e}")

    # -- Final summary --------------------------------------------------------─
    elapsed = time.time() - t_start
    header("Simulation Complete")

    total_points = sum(len(v) for v in all_results.values())
    row("Total scenarios run",     len(all_results))
    row("Total data points",       total_points)
    row("Total time",              f"{elapsed:.2f}", "seconds")
    row("Results directory",       OUTPUT_DIR)
    row("Results JSON",            json_path)
    row("Plots generated",         "[OK] YES" if HAS_MATPLOTLIB and not args.no_plots else "No (install matplotlib)")
    print()


if __name__ == "__main__":
    main()
