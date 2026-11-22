import unittest

from recovery_witness.investigator import InvestigationInput, investigate
from recovery_witness.sealing import chain_events


class DirectEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.event = dict(source="bench", event_type="diagnostic_request", sequence=1,
                          case_id="case", run_id="attempt", observed=True,
                          clock_domain="simulated", schema_version="event.v1")

    def investigate(self, events):
        return investigate(InvestigationInput("case", ("Startup failure",), tuple(events)))

    def test_raw_and_chained_public_observations(self):
        for events in ([self.event], chain_events([self.event])):
            self.assertEqual(self.investigate(events)["observations"][1], events[0])

    def test_incompatible_evidence_is_rejected(self):
        for field, value in (("case_id", "another"), ("sequence", True),
                             ("observed", "yes"), ("extra", "unexpected")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.investigate([dict(self.event, **{field: value})])
        with self.assertRaises(ValueError):
            self.investigate([self.event, dict(self.event, sequence=2, run_id="other")])
        chained = chain_events([self.event])
        chained[0]["event_type"] = "transport_recovered"
        with self.assertRaises(ValueError):
            self.investigate(chained)
