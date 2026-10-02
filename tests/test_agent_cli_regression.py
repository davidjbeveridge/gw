"""Keep ordinary CLI commands working alongside the optional agent surface."""
import io
import json
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout
from gw_supervisor.cli import main


class AgentCLIRegressionTests(unittest.TestCase):
    def test_doctor_and_agent_guide_do_not_shadow_importlib(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = str(pathlib.Path(tmp) / "state")
            for command in (["doctor", "--project", tmp], ["agent-guide"], ["doctor", "--project", tmp]):
                output = io.StringIO()
                with redirect_stdout(output):
                    main(["--home", home, *command])
                if command[0] == "doctor":
                    result = json.loads(output.getvalue())
                    self.assertEqual(result["decision_provider"], "off")
                    self.assertIn("litellm_installed", result)
                else:
                    self.assertIn("gw_status", output.getvalue())
