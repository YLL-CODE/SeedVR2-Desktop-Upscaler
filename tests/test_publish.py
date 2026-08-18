from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app.worker import publish_result


class PublishTests(unittest.TestCase):
    def test_png_publish_failure_cleans_new_report_and_temp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            staged = root / "staged.png"
            staged.write_bytes(b"png")
            output = root / "result.png"
            real_replace = os.replace

            def replace(source: str | bytes | os.PathLike[str], target: str | bytes | os.PathLike[str]) -> None:
                if Path(target).suffix == ".png":
                    raise OSError("simulated publish failure")
                real_replace(source, target)

            report = {"timings": {}}
            with patch("app.worker.os.replace", side_effect=replace):
                with self.assertRaises(OSError):
                    publish_result(staged, output, report, time.perf_counter())
            self.assertFalse(output.exists())
            self.assertFalse(output.with_suffix(".json").exists())
            self.assertFalse(list(root.glob(".*.tmp.png")))


if __name__ == "__main__":
    unittest.main()
