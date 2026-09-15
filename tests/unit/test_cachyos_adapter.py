"""Pruebas unitarias para CachyOSAdapter."""

import os
import tempfile
import unittest
from kwiaty.platform.cachyos import CachyOSAdapter


class TestCachyOSAdapter(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()

        # Crear mock /proc/meminfo
        self.mock_meminfo = os.path.join(self.tmp_dir.name, "meminfo")
        with open(self.mock_meminfo, "w", encoding="utf-8") as f:
            f.write(
                "MemTotal:       16384000 kB\n"
                "MemFree:         4096000 kB\n"
                "MemAvailable:   12288000 kB\n"
                "Buffers:          200000 kB\n"
                "Cached:          8000000 kB\n"
            )

        # Crear mock /proc/uptime
        self.mock_uptime = os.path.join(self.tmp_dir.name, "uptime")
        with open(self.mock_uptime, "w", encoding="utf-8") as f:
            f.write("12345.67 89012.34\n")

        # Crear mock /etc/os-release
        self.mock_os_release = os.path.join(self.tmp_dir.name, "os-release")
        with open(self.mock_os_release, "w", encoding="utf-8") as f:
            f.write(
                'NAME="CachyOS Linux"\n'
                'ID=cachyos\n'
                'PRETTY_NAME="CachyOS Linux Rolling"\n'
            )

        self.adapter = CachyOSAdapter(
            proc_dir=self.tmp_dir.name,
            os_release_path=self.mock_os_release,
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_memory_calculation_mock(self):
        """RF-SYS-04: Cálculo preciso de métricas de memoria en bytes y MB."""
        metrics = self.adapter.get_memory_info()
        # 16384000 kB = 16777216000 bytes
        self.assertEqual(metrics.total_bytes, 16384000 * 1024)
        self.assertEqual(metrics.available_bytes, 12288000 * 1024)
        # used = total - available = 4096000 kB = 4194304000 bytes
        self.assertEqual(metrics.used_bytes, 4096000 * 1024)
        # used_percent = 4096000 / 16384000 = 25.0%
        self.assertEqual(metrics.used_percent, 25.0)

    def test_system_status_mock(self):
        """RF-DIAG-01: Estado consolidado del sistema con mock."""
        status = self.adapter.get_system_status()
        self.assertEqual(status.os_id, "cachyos")
        self.assertEqual(status.os_name, "CachyOS Linux Rolling")
        self.assertEqual(status.uptime_seconds, 12345.67)
        self.assertGreater(status.memory.total_mb, 0)

    def test_real_system_adapter(self):
        """RF-PLAT-01: Verificación sobre el CachyOS real del entorno."""
        real_adapter = CachyOSAdapter()
        status = real_adapter.get_system_status()
        self.assertIsNotNone(status.kernel_release)
        self.assertGreater(status.memory.total_bytes, 0)
        self.assertGreater(status.memory.available_bytes, 0)
        self.assertLessEqual(status.memory.used_percent, 100.0)


if __name__ == "__main__":
    unittest.main()
