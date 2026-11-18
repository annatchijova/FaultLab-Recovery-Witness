import unittest
from pathlib import Path

from recovery_witness.harness import (
    build_case_file,
    parse_public_events,
    validate_artifact_paths,
    verify_case_file,
)


class HarnessContractTests(unittest.TestCase):
    def test_public_event_parser_rejects_oracle_fields(self):
        public_lines = (
            '{"schema_version":"event.v1","source":"bench",'
            '"sequence":1,"event_type":"response_timeout",'
            '"fault":"power_drop"}'
        )

        with self.assertRaises(ValueError):
            parse_public_events(public_lines)

    def test_public_event_parser_returns_only_bench_events(self):
        public_lines = (
            '{"schema_version":"event.v1","source":"bench",'
            '"sequence":1,"event_type":"diagnostic_request",'
            '"clock_domain":"simulated","observed":true}\n'
            '{"schema_version":"event.v1","source":"bench",'
            '"sequence":2,"event_type":"response_timeout",'
            '"clock_domain":"simulated","observed":true}\n'
        )

        events = parse_public_events(public_lines)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["event_type"], "diagnostic_request")
        self.assertEqual(events[1]["sequence"], 2)

    def test_case_file_contains_payload_and_verifiable_seal(self):
        payload = {
            "schema_version": "case-file.v1",
            "case_id": "case-004",
            "decision": "ABSTAIN",
        }

        case_file = build_case_file(payload)

        self.assertEqual(case_file["schema_version"], "sealed-case-file.v1")
        self.assertEqual(case_file["payload"], payload)
        self.assertEqual(len(case_file["sha256"]), 64)
        self.assertTrue(verify_case_file(case_file))

    def test_public_event_parser_rejects_nested_hidden_data_and_unknown_fields(self):
        line = (
            '{"schema_version":"event.v1","source":"bench",'
            '"sequence":1,"event_type":"response_timeout",'
            '"metadata":{"oracle":"secret"}}'
        )
        with self.assertRaises(ValueError):
            parse_public_events(line)

        line = (
            '{"schema_version":"event.v1","source":"bench",'
            '"sequence":1,"event_type":"response_timeout",'
            '"unexpected":true}'
        )
        with self.assertRaises(ValueError):
            parse_public_events(line)

    def test_artifact_paths_must_not_collide(self):
        with self.assertRaises(ValueError):
            validate_artifact_paths(
                path=Path("case.json"), oracle_file=Path("case.json")
            )


if __name__ == "__main__":
    unittest.main()
