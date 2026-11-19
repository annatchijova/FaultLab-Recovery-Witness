import unittest

from recovery_witness.sealing import (
    canonical_bytes,
    chain_events,
    seal,
    verify_event_chain,
)


class SealingTests(unittest.TestCase):
    def test_key_order_does_not_change_canonical_bytes_or_seal(self):
        first = {"case_id": "case-001", "decision": "ABSTAIN", "count": 2}
        second = {"count": 2, "decision": "ABSTAIN", "case_id": "case-001"}

        self.assertEqual(canonical_bytes(first), canonical_bytes(second))
        self.assertEqual(seal(first), seal(second))

    def test_float_is_rejected_from_the_sealed_path(self):
        with self.assertRaises(TypeError):
            canonical_bytes({"score": 0.5})

    def test_non_string_dictionary_keys_are_rejected(self):
        with self.assertRaises(TypeError):
            canonical_bytes({1: "not a schema key"})

    def test_seal_changes_when_payload_changes(self):
        self.assertNotEqual(
            seal({"decision": "ABSTAIN"}),
            seal({"decision": "SUPPORTED"}),
        )

    def test_event_chain_detects_reordering(self):
        events = chain_events(
            [
                {"sequence": 1, "event_type": "start"},
                {"sequence": 2, "event_type": "stop"},
            ]
        )

        report = verify_event_chain(events)
        self.assertTrue(report["linkage_ok"])
        self.assertTrue(report["integrity_ok"])

        reordered = [events[1], events[0]]
        report = verify_event_chain(reordered)
        self.assertFalse(report["linkage_ok"])
        self.assertTrue(report["integrity_ok"])


if __name__ == "__main__":
    unittest.main()
