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
from .mechanic_record import MechanicRecord
from .narrator import narrate, null_narrator
from .narrator_openai import DEFAULT_API_KEY_ENV, DEFAULT_MODEL, make_openai_narrator


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a Recovery Witness host investigation")
    parser.add_argument("--bench", type=Path, required=True)
    parser.add_argument("--fault", required=True)
    parser.add_argument("--oracle-file", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--run-id", help="Execution identifier (generated when omitted); fix for replay")
    parser.add_argument("--mechanic-observation", action="append", default=[])
    parser.add_argument(
        "--dtc", action="append", default=[], dest="dtcs",
        help="A reported diagnostic trouble code (e.g. U0100). Repeatable.",
    )
    parser.add_argument("--scanner-report", help="Free-text scanner report, if any.")
    parser.add_argument(
        "--freeze-frame", metavar="JSON",
        help='Freeze-frame data as a JSON object, e.g. \'{"ignition":"on","rpm":850}\'. No floats.',
    )
    parser.add_argument(
        "--measurement", action="append", default=[], dest="measurements", metavar="JSON",
        help='A measurement as a JSON object: \'{"name":"battery_voltage","value":"12","unit":"V"}\'. '
        "Repeatable. No floats.",
    )
    parser.add_argument(
        "--mechanic-history", action="append", default=[], dest="mechanic_history",
        help="A prior test result or repair history entry. Repeatable.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interactive", action="store_true", help="Request observations from a running bench")
    parser.add_argument("--query", action="store_true", help="Query the next simulated event before advancing")
    parser.add_argument(
        "--narrative-output",
        type=Path,
        help="Write a case-narrative.v1 artifact beside the sealed case file. "
        "It is produced after sealing and never alters the sealed case file.",
    )
    parser.add_argument(
        "--narrator-backend",
        choices=("null", "openai"),
        default="null",
        help="Narration backend (default: offline deterministic template).",
    )
    parser.add_argument(
        "--narrator-model",
        default=DEFAULT_MODEL,
        help="Model name for the openai narrator backend.",
    )
    parser.add_argument(
        "--narrator-api-key-env",
        default=DEFAULT_API_KEY_ENV,
        help="Environment variable holding the OpenAI API key for the openai narrator backend. "
        "The key is read at call time and never logged.",
    )
    return parser


def _select_narrator(args):
    if args.narrator_backend == "openai":
        return make_openai_narrator(model=args.narrator_model, api_key_env=args.narrator_api_key_env)
    return null_narrator


def _build_mechanic_record(args) -> MechanicRecord | None:
    if not (args.dtcs or args.scanner_report or args.freeze_frame
            or args.measurements or args.mechanic_history):
        return None
    try:
        freeze_frame = json.loads(args.freeze_frame) if args.freeze_frame is not None else None
        measurements = tuple(json.loads(item) for item in args.measurements)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in --freeze-frame or --measurement: {error}") from error
    return MechanicRecord(
        dtcs=tuple(args.dtcs),
        scanner_report=args.scanner_report,
        freeze_frame=freeze_frame,
        measurements=measurements,
        history=tuple(args.mechanic_history),
    )


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
            mechanic_record=_build_mechanic_record(args),
        )
    )
    if acquisition is not None:
        payload["acquisition"] = acquisition
    return payload


def main() -> int:
    args = _parser().parse_args()
    validate_request(args.case_id, tuple(args.mechanic_observation))
    validate_artifact_paths(
        path=args.output, oracle_file=args.oracle_file, narrative_output=args.narrative_output
    )
    run_id = args.run_id if args.run_id is not None else uuid.uuid4().hex
    narrative_paths = (args.narrative_output,) if args.narrative_output is not None else ()
    for path in (args.output, args.oracle_file, *narrative_paths):
        if os.path.lexists(path):
            raise FileExistsError(f"Artifact destination already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
    with (tempfile.TemporaryDirectory(dir=args.oracle_file.parent) as oracle_dir,
          tempfile.TemporaryDirectory(dir=args.output.parent) as case_dir):
        pending = Path(oracle_dir) / "oracle.json"
        payload = _capture(args, run_id, pending)
        sealed_case_file = build_case_file(payload)
        case = Path(case_dir) / "case.json"
        write_case_file(case, sealed_case_file)
        os.link(pending, args.oracle_file)
        try:
            os.link(case, args.output)
        except BaseException:
            if pending.samefile(args.oracle_file):
                args.oracle_file.unlink()
            raise
    if args.narrative_output is not None:
        # Narration runs strictly after the case file is sealed and published;
        # it can never influence the sealed payload or its digest, and a
        # narration failure here must not be allowed to undo the publication
        # above.
        write_case_file(args.narrative_output, narrate(sealed_case_file, _select_narrator(args)))
    print(json.dumps({"case_file": str(args.output), "run_id": run_id, "decision": payload["decision"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
