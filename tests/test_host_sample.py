import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from recovery_witness.harness import build_case_file
from recovery_witness.sealing import chain_events

TOOL = Path(__file__).resolve().parents[1] / "tools" / "compare_host_sample.py"


class HostSampleTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.case = Path(folder.name) / "case"
        self.sample = Path(folder.name) / "sample"
        events = chain_events([dict(source="bench", case_id="c", run_id="r", clock_domain="simulated",
                                    observed=True, sequence=i, event_type=name)
                               for i, name in enumerate(("diagnostic_request", "response_timeout", "module_restart"), 1)])
        query = dict(command="CHECK_RESTART", event_type="module_restart", sequence=3, observed=True)
        payload = dict(schema_version="case-file.v1", case_id="c", observations=events,
                       acquisition=dict(schema_version="host-acquisition.v2", protocol="query/NEXT/END", checks=[query]))
        self.case.write_text(json.dumps(build_case_file(payload)))
        self.fields = dict(schema_version="host-recorder-sample.v1", case_id="c", run_id="r", sequence=3,
                           clock_domain="simulated", event_type="module_restart", recorder="test", observed=True)

    def invoke(self, **fields):
        self.sample.write_text(json.dumps({**self.fields, **fields}))
        return subprocess.run([sys.executable, TOOL, self.case, self.sample], capture_output=True, text=True)

    def test_aligned_outcomes(self):
        for value, status in ((True, "AGREES"), (False, "DISAGREES"), (None, "UNKNOWN")):
            self.assertEqual(json.loads(self.invoke(observed=value).stdout)["comparison"], status)

    def test_invalid_references_and_values(self):
        for fields in (dict(run_id="other"), dict(event_type="recovery_started"), dict(observed=1)):
            self.assertNotEqual(self.invoke(**fields).returncode, 0)

    def test_altered_case(self):
        case = json.loads(self.case.read_bytes())
        case["payload"]["acquisition"]["checks"][0]["observed"] = False
        self.case.write_text(json.dumps(case))
        self.assertNotEqual(self.invoke().returncode, 0)
