"""
ns3_bridge.py
=============
Python ↔ Real NS-3 Bridge (Windows → WSL)

Handles:
  - Copying the C++ simulation script into NS-3's scratch/ directory
  - Building it with `./ns3 build`
  - Running it with `./ns3 run` and forwarding scenario arguments
  - Reading the CSV output back into Python
  - Reporting any build or runtime errors clearly

Usage:
    from ns3_real.ns3_bridge import NS3Bridge
    bridge = NS3Bridge()
    bridge.verify()
    results = bridge.run_scenario("fiber_10km")
"""

import csv
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

# -- Valid scenario names (whitelist for shell-injection prevention) -----------

_VALID_SCENARIOS = frozenset({
    'fiber_10km', 'fiber_50km', 'fiber_100km', 'satellite_leo',
    'eve_attack', 'distance_sweep', 'tls_handshake', 'custom',
})

# -- Paths --------------------------------------------------------------------

# Location of this file inside the repo
_HERE = Path(__file__).parent

# The C++ simulation script (lives next to this file)
CC_SCRIPT = _HERE / "qkd_ns3_simulation.cc"

# Where NS-3 is installed inside WSL
NS3_WSL_ROOT = "/home/lenovo/ns-3-dev"

# Name we copy the script to inside NS-3 scratch/
SCRATCH_NAME = "qkd_ns3_simulation"

# Windows temp folder (used for CSV output bridged through WSL)
WIN_TEMP = Path(tempfile.gettempdir())

# -- Helper: run a WSL command, return (stdout, stderr, returncode) ------------

def _wsl(cmd: str, cwd: Optional[str] = None, timeout: int = 300):
    """Run a bash command inside WSL, return (stdout, stderr, returncode)."""
    full_cmd = ["wsl", "bash", "-c", cmd]
    result = subprocess.run(
        full_cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=cwd,
    )
    return result.stdout, result.stderr, result.returncode


def _wsl_path(windows_path: Path) -> str:
    """Convert Windows path to WSL /mnt/ path."""
    p = str(windows_path).replace("\\", "/")
    # e.g. C:/Users/... → /mnt/c/Users/...
    if len(p) >= 2 and p[1] == ":":
        drive = p[0].lower()
        rest = p[2:]
        return f"/mnt/{drive}{rest}"
    return p


# -- Main bridge class --------------------------------------------------------

class NS3Bridge:
    """
    Interface between Windows Python and real NS-3 running in WSL.

    Steps when you call run_scenario():
      1. Copy qkd_ns3_simulation.cc → WSL NS-3 scratch/ folder
      2. Run `./ns3 build scratch/qkd_ns3_simulation`
      3. Run `./ns3 run "qkd_ns3_simulation --scenario=… --output=…"`
      4. Read the CSV written by NS-3
      5. Return list of dicts with parsed results
    """

    def __init__(self, ns3_root: str = NS3_WSL_ROOT):
        self.ns3_root   = ns3_root
        self.cc_src     = CC_SCRIPT
        self.cc_dst_wsl = f"{ns3_root}/scratch/{SCRATCH_NAME}.cc"
        self._built     = False

    # ------------------------------------------------------------------------─
    # Input validation
    # ------------------------------------------------------------------------─

    @staticmethod
    def _validate_inputs(
        scenario: str,
        distance_km,
        bandwidth_mbps: float,
        eve_intercept_rate: float,
        sim_duration_s: float,
    ):
        """Validate run_scenario() inputs to prevent shell injection and bad values."""
        if scenario not in _VALID_SCENARIOS:
            raise ValueError(
                f"Unknown scenario: {scenario!r}. "
                f"Valid scenarios: {sorted(_VALID_SCENARIOS)}"
            )
        for name, val, lo, hi in [
            ("distance_km",        distance_km,        0.1,  2000.0),
            ("bandwidth_mbps",     bandwidth_mbps,     1.0,  100000.0),
            ("eve_intercept_rate", eve_intercept_rate, 0.0,  1.0),
            ("sim_duration_s",     sim_duration_s,     0.5,  3600.0),
        ]:
            if val is not None and not (lo <= float(val) <= hi):
                raise ValueError(
                    f"{name}={val!r} is out of the allowed range [{lo}, {hi}]"
                )

    # ------------------------------------------------------------------------─
    # Public API
    # ------------------------------------------------------------------------─

    def verify(self) -> bool:
        """Check NS-3 installation and print a status report. Returns True if OK."""
        print("=" * 60)
        print("  NS-3 Installation Verification")
        print("=" * 60)

        ok = True

        # 1. WSL available?
        out, err, rc = _wsl("echo WSL_OK")
        if rc != 0 or "WSL_OK" not in out:
            print("  [FAIL] WSL not available or not responding")
            return False
        print("  [OK]   WSL2 is running")

        # 2. NS-3 directory exists?
        out, err, rc = _wsl(f"test -d {self.ns3_root} && echo DIR_OK")
        if rc != 0 or "DIR_OK" not in out:
            print(f"  [FAIL] NS-3 not found at: {self.ns3_root}")
            ok = False
        else:
            print(f"  [OK]   NS-3 found at: {self.ns3_root}")

        # 3. ./ns3 script exists?
        out, err, rc = _wsl(f"test -f {self.ns3_root}/ns3 && echo NS3_OK")
        if rc != 0 or "NS3_OK" not in out:
            print(f"  [FAIL] ./ns3 build script not found")
            ok = False
        else:
            print("  [OK]   ./ns3 build script present")

        # 4. Quick build test
        out, err, rc = _wsl(
            f"cd {self.ns3_root} && ./ns3 run scratch/my-first.cc 2>&1 | tail -3",
            timeout=60
        )
        if "My First ns-3" in out or "ninja: no work" in out:
            print("  [OK]   NS-3 build system is working")
        else:
            print("  [WARN] Could not verify NS-3 build - may need to run ./ns3 build first")

        # 5. C++ script available?
        if not self.cc_src.exists():
            print(f"  [FAIL] C++ script not found: {self.cc_src}")
            ok = False
        else:
            print(f"  [OK]   C++ script found: {self.cc_src.name}")

        # 6. Key modules
        out, err, rc = _wsl(f"ls {self.ns3_root}/src/", timeout=10)
        required = ["point-to-point", "flow-monitor", "applications", "internet"]
        for mod in required:
            if mod in out:
                print(f"  [OK]   Module: {mod}")
            else:
                print(f"  [WARN] Module may be missing: {mod}")

        print()
        if ok:
            print("  [OK] NS-3 is ready. You can run simulations.\n")
        else:
            print("  [FAIL] Some checks failed - see above.\n")
        return ok

    def build(self, force: bool = False) -> bool:
        """Copy the C++ script to NS-3 scratch/ and build it."""
        if self._built and not force:
            return True

        print("[Bridge] Installing simulation script into NS-3 scratch/...")

        # Convert Windows path to WSL /mnt/... path
        wsl_src = _wsl_path(self.cc_src)

        # Copy to NS-3 scratch/
        cp_cmd = f"cp '{wsl_src}' '{self.cc_dst_wsl}'"
        out, err, rc = _wsl(cp_cmd)
        if rc != 0:
            print(f"[Bridge] ERROR copying script:\n{err}")
            return False
        print(f"[Bridge] Copied to: {self.cc_dst_wsl}")

        # Build
        print("[Bridge] Building (this may take 30-60 seconds first time)...")
        build_cmd = f"cd {self.ns3_root} && ./ns3 build scratch/{SCRATCH_NAME} 2>&1"
        out, err, rc = _wsl(build_cmd, timeout=180)

        # Print relevant build output
        for line in out.splitlines():
            if any(k in line for k in ["error:", "warning:", "Built", "ninja", "Compiling", "Linking"]):
                print(f"  {line}")

        if rc != 0:
            print(f"[Bridge] BUILD FAILED (exit code {rc})")
            print(out[-3000:] if len(out) > 3000 else out)
            return False

        print("[Bridge] Build successful.\n")
        self._built = True
        return True

    def run_scenario(
        self,
        scenario: str,
        distance_km: Optional[float] = None,
        bandwidth_mbps: float = 1000.0,
        eve_intercept_rate: float = 0.0,
        sim_duration_s: float = 5.0,
        output_path: Optional[str] = None,
        verbose: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Run a named scenario in real NS-3.

        Args:
            scenario:           One of: fiber_10km, fiber_50km, fiber_100km,
                                satellite_leo, eve_attack, distance_sweep,
                                tls_handshake, custom
            distance_km:        Override distance (used for 'custom' scenario)
            bandwidth_mbps:     Link bandwidth
            eve_intercept_rate: Eve intercept rate (0.0–1.0)
            sim_duration_s:     Simulation wall-clock duration
            output_path:        Where to write CSV (default: auto temp file)
            verbose:            Enable NS-3 internal logging

        Returns:
            List of result dicts (one per scenario point)
        """
        # Validate inputs before touching any shell commands
        self._validate_inputs(
            scenario, distance_km, bandwidth_mbps, eve_intercept_rate, sim_duration_s
        )

        # Build first
        if not self._built:
            if not self.build():
                raise RuntimeError("NS-3 build failed. Cannot run simulation.")

        # Determine output CSV path
        if output_path is None:
            out_win = WIN_TEMP / f"ns3_{scenario}.csv"
        else:
            out_win = Path(output_path).resolve()
        out_wsl = _wsl_path(out_win)

        # Build argument string.
        # NOTE: do not quote the output path — NS-3 CommandLine passes the value
        # literally, so quotes would become part of the filename. Windows paths
        # under WIN_TEMP and the repo's simulation_results/ have no spaces.
        args = [
            f"--scenario={scenario}",
            f"--output={out_wsl}",
            f"--bandwidth={bandwidth_mbps}",
            f"--intercept={eve_intercept_rate}",
            f"--duration={sim_duration_s}",
        ]
        if distance_km is not None:
            args.append(f"--distance={distance_km}")
        if verbose:
            args.append("--verbose=true")

        args_str = " ".join(args)
        run_cmd = f'cd {self.ns3_root} && ./ns3 run "{SCRATCH_NAME} {args_str}" 2>&1'

        print(f"[Bridge] Running scenario: {scenario}")
        print(f"[Bridge] NS-3 command: ./ns3 run \"{SCRATCH_NAME} {args_str}\"")
        print()

        out, err, rc = _wsl(run_cmd, timeout=600)

        # Print simulation output
        for line in out.splitlines():
            print(f"  {line}")

        if rc != 0:
            print(f"\n[Bridge] Simulation FAILED (exit code {rc})")
            raise RuntimeError(f"NS-3 run failed:\n{out}\n{err}")

        print(f"\n[Bridge] Simulation complete. Reading results from {out_win}...")
        return self._parse_csv(out_win)

    def run_all_scenarios(
        self,
        output_dir: Optional[str] = None,
        sim_duration_s: float = 5.0,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Run all scenarios and return {scenario_name: [results]}.

        Args:
            output_dir: Directory to save all CSVs and final JSON
            sim_duration_s: Duration per scenario
        """
        if output_dir is None:
            output_dir = str(_HERE.parent / "simulation_results" / "ns3_real")

        os.makedirs(output_dir, exist_ok=True)

        scenarios = [
            "fiber_10km",
            "fiber_50km",
            "fiber_100km",
            "satellite_leo",
            "eve_attack",
            "distance_sweep",
            "tls_handshake",
        ]

        all_results: Dict[str, List[Dict[str, Any]]] = {}

        for sc in scenarios:
            print(f"\n{'='*60}")
            print(f"  Scenario: {sc}")
            print(f"{'='*60}")
            csv_path = os.path.join(output_dir, f"{sc}.csv")
            try:
                results = self.run_scenario(
                    sc,
                    sim_duration_s=sim_duration_s,
                    output_path=csv_path,
                )
                all_results[sc] = results
                print(f"  [OK] {len(results)} result row(s) captured")
            except Exception as e:
                print(f"  [ERROR] {sc} failed: {e}")
                all_results[sc] = []

        # Also save combined JSON
        import json
        json_path = os.path.join(output_dir, "all_results.json")
        with open(json_path, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\n[Bridge] All results saved to: {output_dir}/")
        print(f"[Bridge] Combined JSON: {json_path}")

        return all_results

    # ------------------------------------------------------------------------─
    # Private helpers
    # ------------------------------------------------------------------------─

    def _parse_csv(self, csv_path: Path) -> List[Dict[str, Any]]:
        """Parse NS-3 output CSV into list of typed dicts."""
        if not csv_path.exists():
            raise FileNotFoundError(f"NS-3 did not produce output: {csv_path}")

        results = []
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                parsed = {}
                for k, v in row.items():
                    k = k.strip()
                    v = v.strip()
                    try:
                        # Boolean columns
                        if k in ("eve_present", "is_secure"):
                            parsed[k] = v == "1"
                        # Integer columns
                        elif k in ("packets_sent", "packets_recv"):
                            parsed[k] = int(v)
                        # Float columns
                        else:
                            parsed[k] = float(v)
                    except ValueError:
                        parsed[k] = v
                results.append(parsed)

        return results
