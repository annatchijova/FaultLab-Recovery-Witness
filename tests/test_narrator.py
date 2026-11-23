import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from recovery_witness import cli
from recovery_witness.harness import build_case_file, verify_case_file
from recovery_witness.investigator import InvestigationInput, investigate
from recovery_witness.narrator import narrate, null_narrator, render_prompt, build_narration_summary


def _sealed_case_file():
    case = InvestigationInput(
        case_id="case-narr-001",
        mechanic_observations=("Intermittent communication loss during startup",),
        bench_observations=(),
    )
    payload = investigate(case)
    return build_case_file(payload)


def _alternate_narrator(prompt: str) -> str:
    return "ALTERNATE BACKEND: " + prompt.splitlines()[4]


class NarratorTests(unittest.TestCase):
    def test_narration_never_changes_the_seal(self):
        case_file = _sealed_case_file()
        before_payload, before_sha = dict(case_file["payload"]), case_file["sha256"]

        narrate(case_file, narrator=null_narrator)
        narrate(case_file, narrator=_alternate_narrator)

        self.assertEqual(case_file["payload"], before_payload)
        self.assertEqual(case_file["sha256"], before_sha)

    def test_swapping_backend_changes_only_the_prose(self):
        case_file = _sealed_case_file()

        narration_a = narrate(case_file, narrator=null_narrator)
        narration_b = narrate(case_file, narrator=_alternate_narrator)

        self.assertEqual(narration_a["case_id"], narration_b["case_id"])
        self.assertNotEqual(narration_a["text"], narration_b["text"])
        self.assertNotEqual(narration_a["backend"], narration_b["backend"])

    def test_narrator_rejects_unsealed_payload(self):
        case = InvestigationInput(
            case_id="case-narr-002",
            mechanic_observations=("Module stops responding",),
            bench_observations=(),
        )
        payload = investigate(case)

        with self.assertRaises(ValueError):
            narrate(payload, narrator=null_narrator)

    def test_narrator_rejects_hidden_oracle_data_defense_in_depth(self):
        case_file = _sealed_case_file()
        tampered = dict(case_file)
        tampered_payload = dict(tampered["payload"])
        tampered_payload["oracle_truth"] = "power_drop"
        tampered["payload"] = tampered_payload

        with self.assertRaises(ValueError):
            narrate(tampered, narrator=null_narrator)

    def test_prompt_states_figures_are_fixed_and_no_vehicle_diagnosis(self):
        case_file = _sealed_case_file()
        summary = build_narration_summary(case_file)
        prompt = render_prompt(summary)

        self.assertIn("figures below are fixed", prompt)
        self.assertIn("Do not state or imply a diagnosis of the real vehicle", prompt)
        self.assertIn(summary["case_id"], prompt)

    def test_narrator_requires_non_empty_text(self):
        case_file = _sealed_case_file()

        with self.assertRaises(ValueError):
            narrate(case_file, narrator=lambda prompt: "   ")


class CliNarrativeTests(unittest.TestCase):
    def test_narrative_output_is_written_beside_an_unchanged_case_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, oracle, narrative = root / "case.json", root / "oracle.json", root / "narrative.json"
            args = ["cli", "--bench", "unused", "--fault", "message_loss", "--case-id", "a",
                    "--run-id", "b", "--mechanic-observation", "Intermittent communication loss",
                    "--oracle-file", str(oracle), "--output", str(case),
                    "--narrative-output", str(narrative)]

            def capture(cli_args, run_id, pending):
                pending.write_text("hidden oracle")
                return investigate(InvestigationInput(
                    case_id="a",
                    mechanic_observations=("Intermittent communication loss",),
                    bench_observations=(),
                ))

            with patch.object(sys, "argv", args), patch.object(cli, "_capture", side_effect=capture):
                self.assertEqual(cli.main(), 0)

            case_file = json.loads(case.read_text())
            self.assertTrue(verify_case_file(case_file))
            narrative_file = json.loads(narrative.read_text())
            self.assertEqual(narrative_file["schema_version"], "case-narrative.v1")
            self.assertEqual(narrative_file["case_id"], "a")
            self.assertTrue(narrative_file["text"])

    def test_narrator_backend_openai_is_selectable_and_never_touches_the_seal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, oracle, narrative = root / "case.json", root / "oracle.json", root / "narrative.json"
            args = ["cli", "--bench", "unused", "--fault", "message_loss", "--case-id", "a",
                    "--run-id", "b", "--mechanic-observation", "Intermittent communication loss",
                    "--oracle-file", str(oracle), "--output", str(case),
                    "--narrative-output", str(narrative),
                    "--narrator-backend", "openai", "--narrator-api-key-env", "ECU_TEST_CLI_KEY"]

            def capture(cli_args, run_id, pending):
                pending.write_text("hidden oracle")
                return investigate(InvestigationInput(
                    case_id="a",
                    mechanic_observations=("Intermittent communication loss",),
                    bench_observations=(),
                ))

            def fake_narrator(prompt):
                return "openai-backed narration"

            with patch.object(sys, "argv", args), patch.object(cli, "_capture", side_effect=capture), \
                 patch.object(cli, "make_openai_narrator", return_value=fake_narrator) as factory:
                self.assertEqual(cli.main(), 0)

            factory.assert_called_once_with(model=cli.DEFAULT_MODEL, api_key_env="ECU_TEST_CLI_KEY")
            case_file = json.loads(case.read_text())
            self.assertTrue(verify_case_file(case_file))
            narrative_file = json.loads(narrative.read_text())
            self.assertEqual(narrative_file["text"], "openai-backed narration")

    def test_narrative_output_must_not_collide_with_case_or_oracle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, oracle = root / "case.json", root / "oracle.json"
            args = ["cli", "--bench", "unused", "--fault", "message_loss", "--case-id", "a",
                    "--run-id", "b", "--mechanic-observation", "timeout",
                    "--oracle-file", str(oracle), "--output", str(case),
                    "--narrative-output", str(case)]

            with patch.object(sys, "argv", args):
                with self.assertRaises(ValueError):
                    cli.main()


if __name__ == "__main__":
    unittest.main()
