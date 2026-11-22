"""Command-line entry point for the first host investigation loop."""

import argparse
import asyncio
import json
from pathlib import Path

from .harness import (
    build_case_file,
    run_bench,
    validate_artifact_paths,
    write_case_file,
)
from .live import acquire
from .investigator import InvestigationInput, investigate


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a Recovery Witness host investigation")
    parser.add_argument("--bench", type=Path, required=True)
    parser.add_argument("--fault", required=True)
    parser.add_argument("--oracle-file", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--mechanic-observation", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interactive", action="store_true", help="Request observations from a running bench")
    parser.add_argument("--query", action="store_true", help="Query the next simulated event before advancing")
    return parser


def main() -> int:
    args = _parser().parse_args()
    validate_artifact_paths(path=args.output, oracle_file=args.oracle_file)
    acquisition = None
    if args.interactive or args.query:
        public_events, acquisition = asyncio.run(acquire(
            args.bench, args.fault, args.oracle_file, args.case_id, args.case_id, query=args.query
        ))
    else:
        public_events = run_bench(args.bench, args.fault, args.oracle_file,
                                  case_id=args.case_id, run_id=args.case_id)
    payload = investigate(
        InvestigationInput(
            case_id=args.case_id,
            mechanic_observations=tuple(args.mechanic_observation),
            bench_observations=public_events,
        )
    )
    if acquisition is not None:
        payload["acquisition"] = acquisition
    write_case_file(args.output, build_case_file(payload))
    print(json.dumps({"case_file": str(args.output), "decision": payload["decision"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
