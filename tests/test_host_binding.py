import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from recovery_witness.experiment import assess
from recovery_witness.harness import run_bench


class HostBindingTests(unittest.TestCase):
    def test_next_probe_depends_on_visible_prefix(self):
        def event(index, name):
            return dict(source="bench", case_id="a", run_id="b", sequence=index, event_type=name,
                        observed=True, clock_domain="simulated", schema_version="event.v1")
        initial, _ = assess([], "a")
        self.assertEqual(initial["next_bench_probe"]["sequence"], 2)
        for name, candidates in (("response_timeout", {"H1", "H2"}),
                                 ("persistence_interrupted", {"H3"})):
            result, _ = assess([event(1, "diagnostic_request"), event(2, name)], "a")
            self.assertEqual(result["next_bench_probe"]["sequence"], 3)
            self.assertEqual(set(result["next_bench_probe"]["predictions"]), candidates)
            self.assertIsNone(result["matched_hypothesis"])

    def test_harness_checks_requested_identity(self):
        event = dict(schema_version="event.v1", source="bench", case_id="a",
                     run_id="different", sequence=1, event_type="diagnostic_request")
        process = subprocess.CompletedProcess([], 0, json.dumps(event), "")
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory) / "oracle.json"
            oracle.touch()
            with patch("recovery_witness.harness.subprocess.run", return_value=process):
                with self.assertRaisesRegex(ValueError, "identity"):
                    run_bench(Path("bench"), "message_loss", oracle, case_id="a", run_id="b")
