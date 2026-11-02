"""Check benchmark failure reporting and timing units without invoking a model."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("benchmark", Path(__file__).parents[1] / "scripts/benchmark-local-ai.py")
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


class BenchmarkTests(unittest.TestCase):
    def test_nanoseconds_and_rate_are_reported_without_generated_content(self):
        result = {"done": True, "message": {"content": "synthetic reply"},
                  "total_duration": 4_000_000_000, "load_duration": 1_000_000_000,
                  "prompt_eval_duration": 2_000_000_000, "prompt_eval_count": 20,
                  "eval_duration": 1_000_000_000, "eval_count": 10}
        measurement = benchmark.metrics(result, 4.2)
        self.assertEqual(measurement["total_seconds"], 4)
        self.assertEqual(measurement["output_tokens_per_second"], 10)
        self.assertNotIn("synthetic reply", str(measurement))

    def test_incomplete_or_empty_response_cannot_be_a_successful_measurement(self):
        for result in ({"done": False, "message": {"content": "partial"}},
                       {"done": True, "message": {"content": " "}}):
            with self.assertRaises(ValueError):
                benchmark.metrics(result, 1)

    def test_missing_generation_duration_does_not_invent_throughput(self):
        measurement = benchmark.metrics({"done": True, "message": {"content": "ok"}}, 1)
        self.assertIsNone(measurement["output_tokens_per_second"])


if __name__ == "__main__":
    unittest.main()
