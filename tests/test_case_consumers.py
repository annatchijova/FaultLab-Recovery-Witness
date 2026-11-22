"""Schema, integrity and observation guarantees for independent case consumers."""

import json
from pathlib import Path
import sys
import unittest

from recovery_witness.harness import build_case_file
from recovery_witness.investigator import InvestigationInput, investigate

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from review_case import report
from verify_case import host_events, parse_document, verify_document


class CaseConsumerTests(unittest.TestCase):
    def test_mechanic_only_case_is_reviewable_without_bench_attestation(self):
        payload = investigate(InvestigationInput("case", ("Intermittent timeout",), ()))
        document = build_case_file(payload)
        result = verify_document(document)
        self.assertFalse(result["valid"])
        self.assertTrue(result["readable"])
        self.assertEqual(result["bench_event_count"], 0)
        self.assertIsNone(result["event_integrity_ok"])
        self.assertIn("No observations recorded", report(json.dumps(document).encode()))
        with self.assertRaisesRegex(ValueError, "No host events"):
            host_events(payload)

    def test_unsupported_observation_fails_schema_despite_correct_seal(self):
        document = build_case_file({"schema_version": "case-file.v1", "case_id": "case",
                                    "observations": [{"source": "unrecognized"}]})
        result = verify_document(document)
        self.assertTrue(result["case_seal_ok"])
        self.assertFalse(result["case_schema_ok"])
        self.assertFalse(result["valid"])

    def test_historical_projected_events_retain_seal_without_chain(self):
        payload = {"schema_version": "case-file.v1", "case_id": "historic", "observations": [
            {"source": "bench", "event_type": "diagnostic_request", "sequence": 1}
        ]}
        result = verify_document(build_case_file(payload))
        self.assertTrue(result["readable"])
        self.assertTrue(result["case_seal_ok"])
        self.assertIsNone(result["event_linkage_ok"])
        self.assertFalse(result["valid"])

    def test_malformed_payload_and_duplicate_fields(self):
        for document in (None, [], {"payload": []}):
            self.assertFalse(verify_document(document)["valid"])
        with self.assertRaisesRegex(ValueError, "Duplicate JSON field"):
            parse_document(b'{"nested":{"status":true,"status":false}}')

    def test_capture_consumers_require_consistent_typed_metadata(self):
        event = dict(schema_version="event.v1", case_id="case", run_id="run", source="bench",
                     clock_domain="simulated", observed=True, event_type="module_restart", sequence=1)
        for bad_event in (dict(event, sequence=True), dict(event, case_id="other"),
                          dict(event, clock_domain="unknown"), dict(event, observed=False),
                          dict(event, run_id="ré"), dict(event, run_id="r" * 129)):
            with self.subTest(event=bad_event), self.assertRaisesRegex(ValueError, "Invalid host event"):
                host_events({"case_id": "case", "observations": [bad_event]})
