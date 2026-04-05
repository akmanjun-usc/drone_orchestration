import importlib.util
import pathlib
import sys
import types
import unittest


def _load_executor_with_stubs():
    bridge_module = types.ModuleType("drone.bridge")

    class DroneClient:
        pass

    bridge_module.DroneClient = DroneClient
    bridge_module.ConnectionError = RuntimeError
    sys.modules["drone.bridge"] = bridge_module

    registry_module = types.ModuleType("skills.registry")

    def capture_client(client):
        return client

    registry_module.get_skill_functions = lambda: {"capture_client": capture_client}
    sys.modules["skills.registry"] = registry_module

    module_name = "_test_llm_executor"
    sys.modules.pop(module_name, None)

    executor_path = pathlib.Path(__file__).parent / "llm" / "executor.py"
    spec = importlib.util.spec_from_file_location(module_name, executor_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ExecuteCodeTests(unittest.TestCase):
    def test_execute_code_accepts_drone_alias(self):
        executor = _load_executor_with_stubs()
        client = object()

        result = executor.execute_code(
            client,
            "captured = capture_client(drone)\nprint(captured is client)",
        )

        self.assertTrue(result.success)
        self.assertEqual(result.stdout_lines, ["True"])

    def test_execute_code_still_accepts_client_name(self):
        executor = _load_executor_with_stubs()
        client = object()

        result = executor.execute_code(
            client,
            "captured = capture_client(client)\nprint(captured is drone)",
        )

        self.assertTrue(result.success)
        self.assertEqual(result.stdout_lines, ["True"])


if __name__ == "__main__":
    unittest.main()
