"""Pruebas de las tools R0 de diagnóstico ampliado."""

import unittest

from kwiaty.platform.base import CpuMetrics, DiskMetrics, ProcessMetrics
from kwiaty.security.risk import RiskLevel
from kwiaty.tools.diagnostics.cpu_usage import CpuUsageTool
from kwiaty.tools.diagnostics.disk_usage import DiskUsageTool
from kwiaty.tools.diagnostics.top_processes import TopProcessesTool
from kwiaty.tools.registry import ToolRegistry


class FakeAdapter:
    platform_id = "cachyos"

    def __init__(self):
        self.process_calls = 0

    def get_cpu_info(self):
        return CpuMetrics(37.5, 8)

    def get_disk_info(self, path="/"):
        return DiskMetrics(path, 1000, 400, 600, 40.0)

    def get_top_processes(self, sort_by="memory", limit=5):
        self.process_calls += 1
        return [ProcessMetrics(42, "worker", 12.5, 2048)][:limit]


class TestDiagnosticTools(unittest.TestCase):
    def test_cpu_tool_is_r0_and_returns_facts(self):
        tool = CpuUsageTool()

        result = tool.execute({}, FakeAdapter())

        self.assertTrue(result.success)
        self.assertEqual(
            result.data,
            {"used_percent": 37.5, "logical_cpus": 8},
        )
        self.assertEqual(tool.metadata.risk_level, RiskLevel.R0)
        self.assertTrue(tool.metadata.offline_available)

    def test_disk_tool_defaults_to_root(self):
        tool = DiskUsageTool()

        params = ToolRegistry().validate_parameters(tool, {})
        result = tool.execute(params, FakeAdapter())

        self.assertEqual(params, {"path": "/"})
        self.assertEqual(result.data["path"], "/")
        self.assertEqual(result.data["used_bytes"], 400)
        self.assertEqual(tool.metadata.risk_level, RiskLevel.R0)

    def test_process_tool_returns_structured_processes(self):
        tool = TopProcessesTool()

        result = tool.execute(
            {"sort_by": "memory", "limit": 5},
            FakeAdapter(),
        )

        self.assertTrue(result.success)
        self.assertEqual(
            result.data,
            {
                "sort_by": "memory",
                "processes": [
                    {
                        "pid": 42,
                        "name": "worker",
                        "cpu_percent": 12.5,
                        "memory_bytes": 2048,
                    }
                ],
            },
        )
        self.assertEqual(tool.metadata.risk_level, RiskLevel.R0)

    def test_process_tool_rejects_bad_criterion_and_limit(self):
        tool = TopProcessesTool()
        adapter = FakeAdapter()

        bad_criterion = tool.execute(
            {"sort_by": "io", "limit": 5},
            adapter,
        )
        bad_limit = tool.execute(
            {"sort_by": "cpu", "limit": 0},
            adapter,
        )
        excessive_limit = tool.execute(
            {"sort_by": "cpu", "limit": 21},
            adapter,
        )

        self.assertFalse(bad_criterion.success)
        self.assertFalse(bad_limit.success)
        self.assertFalse(excessive_limit.success)
        self.assertEqual(adapter.process_calls, 0)


if __name__ == "__main__":
    unittest.main()
