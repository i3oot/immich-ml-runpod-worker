import importlib
import sys
import types
import unittest


class HandlerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fake_runpod = types.SimpleNamespace(
            serverless=types.SimpleNamespace(start=lambda *_args, **_kwargs: None)
        )
        sys.modules.setdefault("runpod", fake_runpod)
        cls.handler_module = importlib.import_module("handler")

    def test_health_operation(self) -> None:
        result = self.handler_module.handler({"input": {"operation": "health"}})

        self.assertTrue(result["ok"])
        self.assertEqual(result["worker"], "immich-ml-runpod-worker")
        self.assertIn("health", result["supportedOperations"])

    def test_operation_defaults_to_health(self) -> None:
        result = self.handler_module.handler({"input": {}})

        self.assertTrue(result["ok"])

    def test_operation_is_normalized(self) -> None:
        result = self.handler_module.handler({"input": {"operation": " Health "}})

        self.assertTrue(result["ok"])

    def test_unsupported_operation(self) -> None:
        result = self.handler_module.handler({"input": {"operation": "clip-image"}})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "unsupported_operation")
        self.assertEqual(result["operation"], "clip-image")

    def test_invalid_input(self) -> None:
        result = self.handler_module.handler({"input": "not-an-object"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "invalid_input")


if __name__ == "__main__":
    unittest.main()
