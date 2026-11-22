import asyncio
import json
import unittest
from unittest.mock import AsyncMock, Mock

from recovery_witness.live import _exchange


class QueryProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def capture(self, second, third, answer):
        reader = asyncio.StreamReader()
        for index, name in enumerate(("diagnostic_request", second, third), 1):
            if index == 3:
                reader.feed_data(answer)
            event = dict(schema_version="event.v1", source="bench", sequence=index, case_id="case",
                         run_id="run", observed=True, clock_domain="simulated", event_type=name)
            reader.feed_data(json.dumps(event).encode() + b"\n")
        reader.feed_data(b"END\n")
        reader.feed_eof()
        process = Mock(stdout=reader, wait=AsyncMock(return_value=0))
        process.stdin.drain = AsyncMock()
        _, acquisition = await _exchange(process, "case", "run", query=True)
        check, = acquisition["checks"]
        commands = [call.args[0] for call in process.stdin.write.call_args_list]
        self.assertEqual(commands, [b"NEXT\n"] * 2 + [check["command"].encode() + b"\n"] + [b"NEXT\n"] * 2)
        return check["command"], check["observed"]

    async def test_queries_depend_on_prefix(self):
        self.assertEqual(await self.capture("response_timeout", "transport_recovered", b"NO\n"),
                         ("CHECK_RESTART", False))
        self.assertEqual(await self.capture("persistence_interrupted", "recovery_started", b"YES\n"),
                         ("CHECK_RECOVERY", True))

    async def test_conflicting_answer_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "contradicts"):
            await self.capture("response_timeout", "module_restart", b"NO\n")
