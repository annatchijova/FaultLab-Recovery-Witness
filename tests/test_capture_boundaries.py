import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from recovery_witness import cli, harness, live


def public_event(sequence=1):
    return dict(schema_version="event.v1", case_id="a", run_id="b", source="bench",
                clock_domain="simulated", event_type="diagnostic_request",
                observed=True, sequence=sequence)


class CaptureBoundaryTests(unittest.TestCase):
    def test_public_fields_and_counters_are_typed(self):
        for key in public_event():
            event = public_event()
            del event[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                harness.validate_public_event(event)
        for key, value in (("observed", 1), ("clock_domain", "wall"), ("sequence", True),
                           ("event_type", " "), ("run_id", []), ("case_id", "a/b")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                harness.validate_public_event({**public_event(), key: value})

    def test_parser_limits(self):
        records = [json.dumps(public_event(i)) for i in (1, 2)]
        lines = "\n".join(records)
        with patch.object(harness, "_MAX_PUBLIC_OUTPUT_BYTES", len(lines)), \
             patch.object(harness, "_MAX_EVENT_LINE_LENGTH", len(records[0])), \
             patch.object(harness, "_MAX_EVENT_COUNT", 2):
            self.assertEqual(len(harness.parse_public_events(lines)), 2)
        for field, limit in (("_MAX_PUBLIC_OUTPUT_BYTES", len(lines) - 1),
                             ("_MAX_EVENT_LINE_LENGTH", len(records[0]) - 1),
                             ("_MAX_EVENT_COUNT", 1)):
            with self.subTest(field=field), patch.object(harness, field, limit), self.assertRaises(ValueError):
                harness.parse_public_events(lines)

    def test_aliases_and_unfinished_oracles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sub").mkdir()
            original = root / "oracle"
            original.write_bytes(b"previous")
            alias = root / "hardlink"
            os.link(original, alias)
            for path in (alias, root / "sub" / ".." / "oracle"):
                with self.assertRaises(ValueError):
                    harness.validate_artifact_paths(path=path, oracle_file=original)
            with self.assertRaises(RuntimeError):
                with harness.staged_oracle(original):
                    pass
            with self.assertRaises(ValueError):
                with harness.staged_oracle(original) as pending:
                    pending.write_bytes(b"partial")
                    raise ValueError("capture failed")
            self.assertEqual(original.read_bytes(), b"previous")

    def test_publication_collision_rolls_back_only_our_oracle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, oracle = root / "case", root / "oracle"
            args = ["cli", "--bench", "unused", "--fault", "message_loss", "--case-id", "a",
                    "--run-id", "b", "--mechanic-observation", "timeout",
                    "--oracle-file", str(oracle), "--output", str(case)]

            def capture(args, run_id, pending):
                pending.write_text("new oracle")
                case.write_text("concurrent publisher")
                return {"schema_version": "case-file.v1", "decision": "ABSTAIN"}

            with patch.object(sys, "argv", args), patch.object(cli, "_capture", side_effect=capture):
                with self.assertRaises(FileExistsError):
                    cli.main()
            self.assertEqual(case.read_text(), "concurrent publisher")
            self.assertFalse(oracle.exists())


class StreamBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_batch_stream_budgets_and_timeout(self):
        for stream, field in (("stdout", "_MAX_PUBLIC_OUTPUT_BYTES"),
                              ("stderr", "_MAX_EVENT_LINE_LENGTH")):
            with self.subTest(stream=stream), patch.object(harness, field, 4):
                args = [sys.executable, "-c", f"import sys; sys.{stream}.write('12345')"]
                with self.assertRaisesRegex(RuntimeError, "size limit"):
                    await harness._bounded_batch(args)
        with patch.object(harness, "_BENCH_TIMEOUT_SECONDS", 0.05):
            with self.assertRaisesRegex(RuntimeError, "timeout"):
                await harness._bounded_batch([sys.executable, "-c", "import time; time.sleep(5)"])

    async def test_interactive_rejects_blank_records_and_stream_overruns(self):
        record = json.dumps(public_event()).encode() + b"\n"
        for data, limit, count in ((b"\n", 1000, 1), (record, len(record) - 1, 1),
                                   (record * 2, 2000, 1)):
            reader = asyncio.StreamReader()
            reader.feed_data(data + b"END\n")
            reader.feed_eof()
            process = Mock(stdout=reader, wait=AsyncMock(return_value=0))
            process.stdin.drain = AsyncMock()
            with self.subTest(limit=limit, count=count), \
                 patch.object(live, "_MAX_PUBLIC_OUTPUT_BYTES", limit), \
                 patch.object(live, "_MAX_EVENT_COUNT", count), self.assertRaises(ValueError):
                await live._exchange(process, "a", "b")
