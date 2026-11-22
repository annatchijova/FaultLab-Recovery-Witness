"""Command-line entry point for the first host investigation loop."""

import argparse
import asyncio
import json
import os
import tempfile
import uuid
from pathlib import Path

from .harness import (
    build_case_file,
    run_bench,
    validate_artifact_paths,
    write_case_file,
)
from .live import acquire
from .investigator import InvestigationInput, investigate, validate_request


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a Recovery Witness host investigation")
    parser.add_argument("--bench", type=Path, required=True)
    parser.add_argument("--fault", required=True)
    parser.add_argument("--oracle-file", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--run-id", help="Execution identifier (generated when omitted); fix for replay")
    parser.add_argument("--mechanic-observation", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interactive", action="store_true", help="Request observations from a running bench")
    parser.add_argument("--query", action="store_true", help="Query the next simulated event before advancing")
    return parser


def _capture(args, run_id, pending_oracle):
    acquisition = None
    if args.interactive or args.query:
        public_events, acquisition = asyncio.run(acquire(
            args.bench, args.fault, pending_oracle, args.case_id, run_id, query=args.query
        ))
    else:
        public_events = run_bench(args.bench, args.fault, pending_oracle,
                                  case_id=args.case_id, run_id=run_id)
    payload = investigate(
        InvestigationInput(
            case_id=args.case_id,
            mechanic_observations=tuple(args.mechanic_observation),
            bench_observations=public_events,
        )
    )
    if acquisition is not None:
        payload["acquisition"] = acquisition
    return payload


def main() -> int:
    args = _parser().parse_args()
    validate_request(args.case_id, tuple(args.mechanic_observation))
    validate_artifact_paths(path=args.output, oracle_file=args.oracle_file)
    run_id = args.run_id if args.run_id is not None else uuid.uuid4().hex
    for path in (args.output, args.oracle_file):
        if os.path.lexists(path):
            raise FileExistsError(f"Artifact destination already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
    with (tempfile.TemporaryDirectory(dir=args.oracle_file.parent) as oracle_dir,
          tempfile.TemporaryDirectory(dir=args.output.parent) as case_dir):
        pending = Path(oracle_dir) / "oracle.json"
        payload = _capture(args, run_id, pending)
        case = Path(case_dir) / "case.json"
        write_case_file(case, build_case_file(payload))
        os.link(pending, args.oracle_file)
        try:
            os.link(case, args.output)
        except BaseException:
            if pending.samefile(args.oracle_file):
                args.oracle_file.unlink()
            raise
    print(json.dumps({"case_file": str(args.output), "run_id": run_id, "decision": payload["decision"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
