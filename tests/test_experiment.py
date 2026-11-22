import unittest

from recovery_witness.experiment import assess


class ExperimentTests(unittest.TestCase):
    def test_only_complete_consistent_observations_match(self):
        events = [dict(schema_version="event.v1", observed=True, case_id="case", run_id="run",
                       clock_domain="simulated", sequence=i, event_type=name)
                  for i, name in enumerate(("diagnostic_request", "response_timeout", "transport_recovered"), 1)]
        result, question = assess(events, "case")
        self.assertEqual(result["matched_hypothesis"], "H2")
        self.assertIn("uptime", question)
        for invalid in (events[:-1], events[::-1], events + events[:1],
                        [*events[:-1], dict(events[-1], observed=False)],
                        [*events[:-1], dict(events[-1], run_id="different")]):
            with self.subTest(invalid=invalid):
                self.assertIsNone(assess(invalid, "case")[0]["matched_hypothesis"])
