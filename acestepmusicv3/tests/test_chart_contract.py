import pathlib
import re
import unittest


CHART_ROOT = pathlib.Path(__file__).parents[1]


class ChartContractTest(unittest.TestCase):
    def test_single_worker_enables_real_on_demand_turbo_switch(self):
        server = (CHART_ROOT / "templates" / "server.yaml").read_text(encoding="utf-8")
        self.assertIn("name: ACESTEP_ON_DEMAND_MODEL_LOAD", server)
        self.assertIn('value: "true"', server)
        for name in ("ACESTEP_API_WORKERS", "ACESTEP_QUEUE_WORKERS"):
            self.assertRegex(
                server,
                rf"name: {re.escape(name)}\s+value: \"1\"",
            )


if __name__ == "__main__":
    unittest.main()
