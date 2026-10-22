import unittest
import tempfile
import shutil
from src.memory_manager import MemoryManager
from src.code_mode_executor import CodeModeExecutor
from src.agent import Agent

class TestPersistentMemoryHarness(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.memory = MemoryManager(storage_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_persistence_across_sessions(self):
        self.memory.save_or_update("backend_framework", "FastAPI", "framework")
        self.memory.save_or_update("primary_db", "PostgreSQL", "database")

        new_memory_manager = MemoryManager(storage_dir=self.test_dir)
        convs = new_memory_manager.load_conventions()

        self.assertIn("backend_framework", convs)
        self.assertIn("primary_db", convs)
        self.assertEqual(convs["backend_framework"]["value"], "FastAPI")
        self.assertEqual(convs["primary_db"]["value"], "PostgreSQL")

        injected = new_memory_manager.get_injected_context()
        self.assertIn("FastAPI", injected)
        self.assertIn("PostgreSQL", injected)

    def test_conflict_resolution_and_update(self):
        self.memory.save_or_update("primary_db", "PostgreSQL", "database")
        self.memory.save_or_update("primary_db", "MongoDB", "database", reason="Switch DB")

        convs = self.memory.load_conventions()
        self.assertEqual(convs["primary_db"]["value"], "MongoDB")
        self.assertEqual(convs["primary_db"]["version"], 2)

        history = self.memory._load_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[1]["action"], "UPDATE_OVERWRITE")
        self.assertEqual(history[1]["old_value"], "PostgreSQL")
        self.assertEqual(history[1]["new_value"], "MongoDB")

    def test_code_mode_execution(self):
        executor = CodeModeExecutor(timeout_seconds=3)
        code = "print(sum([1, 2, 3, 4, 5]))"
        res = executor.execute(code)
        self.assertTrue(res["success"])
        self.assertEqual(res["stdout"], "15")

    def test_agent_simulation_flow(self):
        agent = Agent(self.memory, use_mock=True)
        res1 = agent.process_message("Thống nhất dùng PostgreSQL và FastAPI")
        self.assertEqual(len(res1["tool_calls"]), 3)

        res2 = agent.process_message("Đổi sang dùng MongoDB")
        self.assertEqual(len(res2["tool_calls"]), 1)
        self.assertEqual(res2["tool_calls"][0]["name"], "update_convention")

        res3 = agent.process_message("Dùng Code Mode phân tích log")
        self.assertEqual(res3["tool_calls"][0]["name"], "run_code")

if __name__ == "__main__":
    unittest.main()
