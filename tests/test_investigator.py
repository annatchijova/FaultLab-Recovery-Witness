import json
import sys
import unittest
from pathlib import Path

from recovery_witness.harness import build_case_file
from recovery_witness.investigator import InvestigationInput, investigate
from recovery_witness.mechanic_record import MechanicRecord

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from verify_case import verify_document  # noqa: E402


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

    def test_mechanic_record_is_additive_and_independently_verifiable(self):
        case_without_record = InvestigationInput(
            case_id="case-004",
            mechanic_observations=("Intermittent communication loss",),
            bench_observations=(),
        )
        case_with_record = InvestigationInput(
            case_id="case-004",
            mechanic_observations=("Intermittent communication loss",),
            bench_observations=(),
            mechanic_record=MechanicRecord(
                dtcs=("U0100",),
                scanner_report="Communication codes present during startup",
                freeze_frame={"ignition": "on"},
                measurements=({"name": "battery_voltage", "value": "12", "unit": "V"},),
                history=("No prior repairs",),
            ),
        )

        bare_payload = investigate(case_without_record)
        self.assertNotIn("mechanic_record", bare_payload)

        enriched_payload = investigate(case_with_record)
        self.assertEqual(enriched_payload["mechanic_record"]["dtcs"], ["U0100"])
        self.assertEqual(
            {k: v for k, v in enriched_payload.items() if k != "mechanic_record"},
            bare_payload,
        )

        sealed = build_case_file(enriched_payload)
        report = verify_document(sealed)
        self.assertTrue(report["case_schema_ok"])
        self.assertTrue(report["case_seal_ok"])


if __name__ == "__main__":
    unittest.main()
