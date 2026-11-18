import json
import unittest

from recovery_witness.investigator import InvestigationInput, investigate


class InvestigatorContractTests(unittest.TestCase):
    def test_mechanic_observations_are_required(self):
        case = InvestigationInput(
            case_id="case-empty",
            mechanic_observations=(),
            bench_observations=(),
        )

        with self.assertRaises(ValueError):
            investigate(case)

    def test_investigation_preserves_public_evidence_boundary(self):
        case = InvestigationInput(
            case_id="case-001",
            mechanic_observations=(
                "Intermittent communication loss during startup",
                "DTC U0100 recorded after the event",
            ),
            bench_observations=(
                {
                    "event_type": "diagnostic_request",
                    "source": "bench",
                    "sequence": 1,
                },
                {
                    "event_type": "response_timeout",
                    "source": "bench",
                    "sequence": 2,
                },
            ),
        )

        result = investigate(case)

        self.assertEqual(result["schema_version"], "case-file.v1")
        self.assertEqual(result["case_id"], "case-001")
        self.assertNotIn("fault", result)
        self.assertNotIn("oracle_truth", result)
        self.assertNotIn("vehicle_diagnosis", result)
        self.assertGreaterEqual(len(result["hypotheses"]), 2)
        self.assertTrue(result["next_observation"])
        self.assertEqual(
            {observation["source"] for observation in result["observations"]},
            {"mechanic", "bench"},
        )

    def test_hidden_oracle_fields_are_rejected_at_the_boundary(self):
        case = InvestigationInput(
            case_id="case-002",
            mechanic_observations=("Module stops responding intermittently",),
            bench_observations=(
                {
                    "event_type": "response_timeout",
                    "source": "bench",
                    "sequence": 1,
                    "fault": "power_drop",
                },
            ),
        )

        with self.assertRaises(ValueError):
            investigate(case)

    def test_nested_hidden_oracle_fields_are_rejected_at_the_boundary(self):
        case = InvestigationInput(
            case_id="case-nested",
            mechanic_observations=("Module stops responding intermittently",),
            bench_observations=(
                {
                    "event_type": "response_timeout",
                    "source": "bench",
                    "sequence": 1,
                    "metadata": {"oracle": "power_drop"},
                },
            ),
        )

        with self.assertRaises(ValueError):
            investigate(case)

    def test_case_file_is_canonical_json(self):
        case = InvestigationInput(
            case_id="case-003",
            mechanic_observations=("Communication failure",),
            bench_observations=(),
        )

        result = investigate(case)
        encoded = json.dumps(result, sort_keys=True, separators=(",", ":"))

        self.assertEqual(encoded, json.dumps(result, sort_keys=True, separators=(",", ":")))
        self.assertEqual(result["decision"], "ABSTAIN")


if __name__ == "__main__":
    unittest.main()
