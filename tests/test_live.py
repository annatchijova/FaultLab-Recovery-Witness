import asyncio
import json
import unittest
from unittest.mock import AsyncMock, Mock

from recovery_witness.live import _exchange


class LiveProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def exchange(self, suffix, status=0):
        reader = asyncio.StreamReader()
        for i, name in enumerate(("diagnostic_request", "response_timeout", "transport_recovered"), 1):
            event = dict(schema_version="event.v1", source="bench", sequence=i, case_id="case",
                         run_id="run", observed=True, clock_domain="simulated", event_type=name)
            reader.feed_data(json.dumps(event).encode() + b"\n")
        reader.feed_data(suffix)
        reader.feed_eof()
        process = Mock(stdout=reader, wait=AsyncMock(return_value=status))
        process.stdin.drain = AsyncMock()
        return await _exchange(process, "case", "run")

    async def test_complete_signature_still_requires_clean_end(self):
        for suffix, status in ((b"", 0), (b"END\nextra", 0), (b"END\n", 1)):
            with self.subTest(suffix=suffix, status=status):
                with self.assertRaises(ValueError):
                    await self.exchange(suffix, status)

    async def test_live_requests_follow_timeout_branch(self):
        events, acquisition = await self.exchange(b"END\n")
        self.assertEqual(len(events), 3)
        first, second = acquisition["requests"]
        self.assertEqual(first["sequence"], 2)
        self.assertEqual(second["predictions"], {"H1": "module_restart", "H2": "transport_recovered"})
        self.assertEqual(second["returned_event"], "transport_recovered")
