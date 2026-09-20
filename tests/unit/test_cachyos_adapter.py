"""Pruebas unitarias para CachyOSAdapter."""

import os
import tempfile
import unittest
from unittest.mock import patch

from kwiaty.platform.base import DiskMetrics
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

    def _write_cpu_stat(self, busy, idle):
        stat_path = os.path.join(self.tmp_dir.name, "stat")
        with open(stat_path, "w", encoding="utf-8") as stat_file:
            stat_file.write(f"cpu {busy} 0 0 {idle} 0\n")

    def _write_process(self, pid, name, ticks, rss_kb, malformed=False):
        process_dir = os.path.join(self.tmp_dir.name, str(pid))
        os.makedirs(process_dir, exist_ok=True)
        with open(os.path.join(process_dir, "comm"), "w", encoding="utf-8") as file:
            file.write(f"{name}\n")
        with open(os.path.join(process_dir, "status"), "w", encoding="utf-8") as file:
            file.write(f"Name:\t{name}\nVmRSS:\t{rss_kb} kB\n")
        with open(os.path.join(process_dir, "stat"), "w", encoding="utf-8") as file:
            if malformed:
                file.write("invalid stat\n")
            else:
                fields_before_ticks = "S 0 0 0 0 0 0 0 0 0 0"
                file.write(
                    f"{pid} ({name}) {fields_before_ticks} {ticks} 0 "
                    "0 0 0 0 0 0 0 0 0\n"
                )

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

    def test_cpu_usage_uses_two_proc_stat_samples(self):
        stat_path = os.path.join(self.tmp_dir.name, "stat")
        with open(stat_path, "w", encoding="utf-8") as stat_file:
            stat_file.write("cpu 20 0 20 60 0\n")

        def replace_stat(_interval):
            with open(stat_path, "w", encoding="utf-8") as stat_file:
                stat_file.write("cpu 60 0 40 100 0\n")

        adapter = CachyOSAdapter(
            proc_dir=self.tmp_dir.name,
            os_release_path=self.mock_os_release,
            sleep_fn=replace_stat,
        )

        with patch("kwiaty.platform.cachyos.os.cpu_count", return_value=8):
            metrics = adapter.get_cpu_info(sample_interval=0)

        self.assertEqual(metrics.used_percent, 60.0)
        self.assertEqual(metrics.logical_cpus, 8)

    def test_cpu_zero_delta_returns_zero(self):
        stat_path = os.path.join(self.tmp_dir.name, "stat")
        with open(stat_path, "w", encoding="utf-8") as stat_file:
            stat_file.write("cpu 20 0 20 60 0\n")
        adapter = CachyOSAdapter(
            proc_dir=self.tmp_dir.name,
            os_release_path=self.mock_os_release,
            sleep_fn=lambda _interval: None,
        )

        self.assertEqual(adapter.get_cpu_info(sample_interval=0).used_percent, 0.0)

    def test_disk_usage_returns_structured_bytes(self):
        with patch(
            "kwiaty.platform.cachyos.shutil.disk_usage",
            return_value=(1000, 400, 600),
        ):
            metrics = self.adapter.get_disk_info("/tmp")

        self.assertEqual(metrics, DiskMetrics("/tmp", 1000, 400, 600, 40.0))

    def test_disk_usage_handles_zero_total(self):
        with patch(
            "kwiaty.platform.cachyos.shutil.disk_usage",
            return_value=(0, 0, 0),
        ):
            metrics = self.adapter.get_disk_info("/")

        self.assertEqual(metrics.used_percent, 0.0)

    def test_top_processes_orders_by_memory_and_limits(self):
        self._write_cpu_stat(40, 60)
        self._write_process(11, "cpu hog (test)", 10, 100)
        self._write_process(22, "worker", 20, 300)

        def second_sample(_interval):
            self._write_cpu_stat(100, 100)
            self._write_process(11, "cpu hog (test)", 40, 100)
            self._write_process(22, "worker", 30, 300)

        adapter = CachyOSAdapter(
            proc_dir=self.tmp_dir.name,
            os_release_path=self.mock_os_release,
            sleep_fn=second_sample,
        )

        result = adapter.get_top_processes(
            sort_by="memory",
            limit=1,
            sample_interval=0,
        )

        self.assertEqual([(process.pid, process.name) for process in result], [(22, "worker")])
        self.assertEqual(result[0].memory_bytes, 300 * 1024)

    def test_top_processes_orders_by_cpu_from_sample_delta(self):
        self._write_cpu_stat(40, 60)
        self._write_process(11, "cpu hog (test)", 10, 100)
        self._write_process(22, "worker", 20, 300)

        def second_sample(_interval):
            self._write_cpu_stat(100, 100)
            self._write_process(11, "cpu hog (test)", 40, 100)
            self._write_process(22, "worker", 30, 300)

        adapter = CachyOSAdapter(
            proc_dir=self.tmp_dir.name,
            os_release_path=self.mock_os_release,
            sleep_fn=second_sample,
        )

        with patch("kwiaty.platform.cachyos.os.cpu_count", return_value=2):
            result = adapter.get_top_processes(
                sort_by="cpu",
                limit=2,
                sample_interval=0,
            )

        self.assertEqual([process.pid for process in result], [11, 22])
        self.assertEqual(result[0].name, "cpu hog (test)")
        self.assertGreater(result[0].cpu_percent, result[1].cpu_percent)

    def test_disappearing_or_malformed_process_is_skipped(self):
        self._write_cpu_stat(40, 60)
        self._write_process(22, "worker", 20, 300)
        self._write_process(33, "broken", 0, 50, malformed=True)
        self._write_process(44, "short lived", 10, 25)

        def second_sample(_interval):
            self._write_cpu_stat(100, 100)
            self._write_process(22, "worker", 30, 300)
            os.remove(os.path.join(self.tmp_dir.name, "44", "stat"))

        adapter = CachyOSAdapter(
            proc_dir=self.tmp_dir.name,
            os_release_path=self.mock_os_release,
            sleep_fn=second_sample,
        )

        result = adapter.get_top_processes(limit=5, sample_interval=0)

        self.assertEqual([process.pid for process in result], [22])

    def test_top_processes_rejects_invalid_options(self):
        with self.assertRaises(ValueError):
            self.adapter.get_top_processes(sort_by="io")
        with self.assertRaises(ValueError):
            self.adapter.get_top_processes(limit=0)


if __name__ == "__main__":
    unittest.main()
