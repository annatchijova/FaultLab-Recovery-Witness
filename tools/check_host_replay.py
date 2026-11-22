"""Replay every host fixture and check its public signature and case integrity."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SIGNATURES = {
    "power_drop": ("response_timeout", "module_restart", "module_initialized"),
    "message_loss": ("response_timeout", "transport_recovered"),
    "recovery_incomplete": ("persistence_interrupted", "recovery_started", "module_not_ready"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", required=True, type=Path)
    args = parser.parse_args()
    for scenario, signature in SIGNATURES.items():
        for mode in ((), ("--interactive",), ("--query",)):
            copies = []
            for seed in ("1", "2"):
                with tempfile.TemporaryDirectory() as directory:
                    case = Path(directory) / "case.json"
                    run_id = f"replay-{scenario}-{mode[0][2:] if mode else 'batch'}"
                    subprocess.run([
                        sys.executable, "-m", "recovery_witness.cli",
                        "--bench", str(args.bench.resolve()), "--fault", scenario,
                        "--case-id", "host-fixture", "--run-id", run_id, *mode,
                        "--mechanic-observation", "Intermittent loss of communication during startup.",
                        "--oracle-file", str(case.with_name("oracle.json")), "--output", str(case),
                    ], check=True, env={**os.environ, "PYTHONPATH": str(ROOT / "python"),
                                        "PYTHONHASHSEED": seed})
                    subprocess.run([sys.executable, ROOT / "tools/verify_case.py", case], check=True)
                    copies.append(case.read_bytes())
                    payload = json.loads(copies[-1])["payload"]
                    events = tuple(item["event_type"] for item in payload["observations"]
                                   if item["source"] == "bench")
                    if events != ("diagnostic_request", *signature) or payload["decision"] != "ABSTAIN":
                        raise ValueError(f"Unexpected investigation result for {scenario} {mode}")
                    if mode == ("--query",):
                        acquisition = payload["acquisition"]
                        if acquisition["protocol"] != "query/NEXT/END" or not acquisition["checks"]:
                            raise ValueError(f"Query protocol was not exercised for {scenario}")
            if copies[0] != copies[1]:
                raise ValueError(f"Replay differs for {scenario} {mode}")
        print(f"{scenario}: batch, interactive and query signatures verified", flush=True)


if __name__ == "__main__":
    main()
