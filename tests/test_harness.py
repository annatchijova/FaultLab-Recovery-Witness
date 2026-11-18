import unittest

from recovery_witness.harness import build_case_file, parse_public_events


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


if __name__ == "__main__":
    unittest.main()
