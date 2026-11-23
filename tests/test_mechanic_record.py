import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from recovery_witness import cli
from recovery_witness.harness import build_case_file, verify_case_file
from recovery_witness.investigator import InvestigationInput, investigate
from recovery_witness.mechanic_record import MechanicRecord, validate_mechanic_record

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from review_case import report  # noqa: E402


class MechanicRecordTests(unittest.TestCase):
    def test_minimal_record_has_canonical_empty_fields(self):
        result = validate_mechanic_record(MechanicRecord())

        self.assertEqual(result["schema_version"], "mechanic-record.v1")
        self.assertEqual(result["source"], "mechanic")
        self.assertEqual(result["dtcs"], [])
        self.assertEqual(result["measurements"], [])
        self.assertEqual(result["history"], [])
        self.assertIsNone(result["scanner_report"])
        self.assertIsNone(result["freeze_frame"])

    def test_full_record_round_trips(self):
        record = MechanicRecord(
            dtcs=("U0100", "P0300"),
            scanner_report="Communication codes present during startup",
            freeze_frame={"ignition": "on", "rpm": 850},
            measurements=({"name": "battery_voltage", "value": "12", "unit": "V"},),
            history=("Battery replaced six months ago",),
        )

        result = validate_mechanic_record(record)

        self.assertEqual(result["dtcs"], ["U0100", "P0300"])
        self.assertEqual(result["scanner_report"], "Communication codes present during startup")
        self.assertEqual(result["freeze_frame"], {"ignition": "on", "rpm": 850})
        self.assertEqual(result["measurements"], [{"name": "battery_voltage", "value": "12", "unit": "V"}])
        self.assertEqual(result["history"], ["Battery replaced six months ago"])

    def test_rejects_malformed_dtc_codes(self):
        for bad_code in ("0100", "X0100", "U010", "u0100", "U01000"):
            with self.subTest(code=bad_code):
                with self.assertRaises(ValueError):
                    validate_mechanic_record(MechanicRecord(dtcs=(bad_code,)))

    def test_rejects_float_in_freeze_frame(self):
        with self.assertRaisesRegex(ValueError, "must not contain a float"):
            validate_mechanic_record(MechanicRecord(freeze_frame={"battery_voltage": 12.6}))

    def test_rejects_float_nested_in_freeze_frame(self):
        with self.assertRaisesRegex(ValueError, "must not contain a float"):
            validate_mechanic_record(
                MechanicRecord(freeze_frame={"sensors": {"voltage": 12.6}})
            )

    def test_rejects_float_measurement_value(self):
        with self.assertRaises(ValueError):
            validate_mechanic_record(
                MechanicRecord(measurements=({"name": "voltage", "value": 12.6},))
            )

    def test_measurement_requires_name_and_value(self):
        with self.assertRaises(ValueError):
            validate_mechanic_record(MechanicRecord(measurements=({"name": "voltage"},)))

    def test_measurement_rejects_unknown_keys(self):
        with self.assertRaises(ValueError):
            validate_mechanic_record(
                MechanicRecord(measurements=({"name": "voltage", "value": 12, "note": "stray"},))
            )

    def test_rejects_non_mechanic_record_type(self):
        with self.assertRaises(ValueError):
            validate_mechanic_record({"dtcs": []})

    def test_enforces_list_length_limits(self):
        too_many = tuple(f"P030{i}" if i < 10 else "P0300" for i in range(51))
        with self.assertRaises(ValueError):
            validate_mechanic_record(MechanicRecord(dtcs=too_many))


class CliMechanicRecordTests(unittest.TestCase):
    def test_cli_flags_build_a_mechanic_record_in_the_sealed_case_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, oracle = root / "case.json", root / "oracle.json"
            args = [
                "cli", "--bench", "unused", "--fault", "message_loss", "--case-id", "a",
                "--run-id", "b", "--mechanic-observation", "Intermittent communication loss",
                "--dtc", "U0100", "--dtc", "P0300",
                "--scanner-report", "Communication codes during startup",
                "--freeze-frame", '{"ignition": "on"}',
                "--measurement", '{"name": "battery_voltage", "value": "12", "unit": "V"}',
                "--mechanic-history", "No prior repairs",
                "--oracle-file", str(oracle), "--output", str(case),
            ]

            def capture(cli_args, run_id, pending):
                pending.write_text("hidden oracle")
                from recovery_witness.investigator import InvestigationInput, investigate
                return investigate(InvestigationInput(
                    case_id="a",
                    mechanic_observations=("Intermittent communication loss",),
                    bench_observations=(),
                    mechanic_record=cli._build_mechanic_record(cli_args),
                ))

            with patch.object(sys, "argv", args), patch.object(cli, "_capture", side_effect=capture):
                self.assertEqual(cli.main(), 0)

            case_file = json.loads(case.read_text())
            self.assertTrue(verify_case_file(case_file))
            record = case_file["payload"]["mechanic_record"]
            self.assertEqual(record["dtcs"], ["U0100", "P0300"])
            self.assertEqual(record["scanner_report"], "Communication codes during startup")
            self.assertEqual(record["freeze_frame"], {"ignition": "on"})
            self.assertEqual(record["measurements"], [{"name": "battery_voltage", "value": "12", "unit": "V"}])
            self.assertEqual(record["history"], ["No prior repairs"])

    def test_no_mechanic_record_flags_means_no_record(self):
        parser = cli._parser()
        args = parser.parse_args([
            "--bench", "unused", "--fault", "message_loss", "--case-id", "a",
            "--oracle-file", "oracle.json", "--output", "case.json",
        ])

        self.assertIsNone(cli._build_mechanic_record(args))

    def test_invalid_json_in_freeze_frame_raises_a_clear_error(self):
        parser = cli._parser()
        args = parser.parse_args([
            "--bench", "unused", "--fault", "message_loss", "--case-id", "a",
            "--oracle-file", "oracle.json", "--output", "case.json",
            "--freeze-frame", "{not json}",
        ])

        with self.assertRaisesRegex(ValueError, "Invalid JSON"):
            cli._build_mechanic_record(args)


class ReviewRenderingTests(unittest.TestCase):
    def test_review_report_renders_the_mechanic_record_as_not_ground_truth(self):
        case = InvestigationInput(
            case_id="case-review-001",
            mechanic_observations=("Intermittent communication loss",),
            bench_observations=(),
            mechanic_record=MechanicRecord(
                dtcs=("U0100",),
                scanner_report="Communication codes during startup",
                freeze_frame={"ignition": "on"},
                measurements=({"name": "battery_voltage", "value": "12", "unit": "V"},),
                history=("No prior repairs",),
            ),
        )
        sealed = build_case_file(investigate(case))

        text = report(json.dumps(sealed).encode())

        self.assertIn("not vehicle ground truth", text)
        self.assertIn("U0100", text)
        self.assertIn("Communication codes during startup", text)
        self.assertIn("battery_voltage = 12 V", text)
        self.assertIn("No prior repairs", text)


if __name__ == "__main__":
    unittest.main()
