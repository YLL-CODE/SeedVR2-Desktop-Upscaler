from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from PIL import Image


class WorkerHarness:
    def __init__(self, environment: dict[str, str]) -> None:
        self.project = Path(__file__).resolve().parents[1]
        merged = os.environ.copy()
        merged.update(
            {
                "PYTHONPATH": str(self.project),
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONNOUSERSITE": "1",
                "SEEDVR2_FAKE": "1",
                **environment,
            }
        )
        self.process = subprocess.Popen(
            [sys.executable, "-u", "-m", "app.worker"],
            cwd=self.project,
            env=merged,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

    def send(self, command: dict[str, Any]) -> None:
        assert self.process.stdin
        self.process.stdin.write(json.dumps(command, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def read_until(
        self, terminal: set[str], cancel_on_progress: bool = False, cancel_on_assemble: bool = False
    ) -> list[dict[str, Any]]:
        assert self.process.stdout
        events = []
        cancel_sent = False
        for line in self.process.stdout:
            event = json.loads(line)
            events.append(event)
            if cancel_on_progress and event["event"] == "progress" and not cancel_sent:
                self.send({"command": "cancel"})
                cancel_sent = True
            if cancel_on_assemble and event.get("stage") == "assemble" and not cancel_sent:
                self.send({"command": "cancel"})
                cancel_sent = True
            if event["event"] in terminal:
                return events
        return events

    def close(self) -> None:
        if self.process.poll() is None:
            self.send({"command": "shutdown"})
            self.process.wait(timeout=20)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if stream:
                stream.close()


class WorkerTests(unittest.TestCase):
    def test_worker_messages_follow_language_and_can_switch_at_runtime(self) -> None:
        worker = WorkerHarness({"SEEDVR2_LANGUAGE": "en"})
        try:
            startup = worker.read_until({"ready", "error"})
            self.assertEqual(startup[-1]["event"], "ready", startup[-1])
            self.assertEqual(startup[-1]["message"], "The Worker is ready.")
            worker.send({"command": "set_language", "language": "xx"})
            invalid = worker.read_until({"error"})
            self.assertEqual(invalid[-1]["message"], "Unsupported display language: xx")
            worker.send({"command": "set_language", "language": "zh_CN"})
            worker.send({"command": "not-a-command"})
            switched = worker.read_until({"error"})
            self.assertIn("未知 Worker 指令", switched[-1]["message"])
        finally:
            worker.close()

    def test_two_tasks_use_ascii_tiles_and_distinct_logs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "中文图片.png"
            output = root / "中文输出"
            Image.new("RGB", (96, 72), "orange").save(source)
            worker = WorkerHarness({})
            try:
                terminal_events = []
                task_events = []
                for _ in range(2):
                    worker.send({"command": "run", "source": str(source), "outputDir": str(output)})
                    events = worker.read_until({"completed", "error"})
                    self.assertEqual(events[-1]["event"], "completed", events[-1])
                    task_events.append(events)
                    terminal_events.append(events[-1])
                logs = [Path(event["metrics"]["log"]) for event in terminal_events]
                self.assertNotEqual(logs[0], logs[1])
                for log in logs:
                    self.assertTrue(log.is_file())
                    for line in log.read_text(encoding="utf-8").splitlines():
                        self.assertTrue(line.isascii(), line)
                self.assertNotEqual(terminal_events[0]["output"], terminal_events[1]["output"])
                self.assertEqual(terminal_events[0]["metrics"]["scale"], 4)
                self.assertEqual(terminal_events[0]["metrics"]["gridPreset"], "3x3")
                self.assertEqual(terminal_events[0]["metrics"]["tiles"], [3, 3])
                self.assertEqual(sum(event["event"] == "model_ready" for event in task_events[0]), 1)
                self.assertEqual(sum(event["event"] == "model_ready" for event in task_events[1]), 0)
            finally:
                worker.close()

    def test_cancel_event_stays_on_json_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            Image.new("RGB", (96, 72), "green").save(source)
            worker = WorkerHarness({"SEEDVR2_FAKE_DELAY": "0.15"})
            try:
                worker.send({"command": "run", "source": str(source), "outputDir": str(root / "out")})
                events = worker.read_until({"cancelled", "completed", "error"}, cancel_on_progress=True)
                self.assertEqual(events[-1]["event"], "cancelled", events[-1])
                self.assertIn("cancel_requested", {event["event"] for event in events})
                self.assertFalse(list((root / "out").glob("*.png")))
            finally:
                worker.close()

    def test_scale_and_grid_presets_reach_output_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            Image.new("RGB", (96, 72), "purple").save(source)
            worker = WorkerHarness({})
            try:
                worker.send(
                    {
                        "command": "run",
                        "source": str(source),
                        "outputDir": str(root / "out"),
                        "scale": 2,
                        "grid": "4x4",
                    }
                )
                events = worker.read_until({"completed", "error"})
                completed = events[-1]
                self.assertEqual(completed["event"], "completed", completed)
                self.assertTrue(completed["output"].endswith("-seedvr2-2x.png"))
                self.assertEqual(completed["metrics"]["outputSize"], [192, 144])
                self.assertEqual(completed["metrics"]["scale"], 2)
                self.assertEqual(completed["metrics"]["gridPreset"], "4x4")
                self.assertEqual(completed["metrics"]["tiles"], [4, 4])
            finally:
                worker.close()

    def test_invalid_preset_fails_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            Image.new("RGB", (96, 72), "black").save(source)
            worker = WorkerHarness({})
            try:
                worker.send(
                    {"command": "run", "source": str(source), "outputDir": str(root / "out"), "scale": 3}
                )
                events = worker.read_until({"completed", "error"})
                self.assertEqual(events[-1]["event"], "error", events[-1])
                self.assertFalse(list((root / "out").glob("*.png")))
            finally:
                worker.close()

    def test_cancel_during_assemble_does_not_publish(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            Image.new("RGB", (96, 72), "blue").save(source)
            worker = WorkerHarness({"SEEDVR2_FAKE_ASSEMBLE_DELAY": "0.15"})
            try:
                worker.send({"command": "run", "source": str(source), "outputDir": str(root / "out")})
                events = worker.read_until({"cancelled", "completed", "error"}, cancel_on_assemble=True)
                self.assertEqual(events[-1]["event"], "cancelled", events[-1])
                self.assertFalse(list((root / "out").glob("*.png")))
            finally:
                worker.close()

    def test_startup_failure_is_json_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            worker = WorkerHarness({"SEEDVR2_MODEL_DIR": str(Path(directory) / "missing")})
            try:
                events = worker.read_until({"error"})
                worker.process.wait(timeout=10)
                self.assertEqual(events[-1]["event"], "error")
                self.assertNotEqual(worker.process.returncode, 0)
            finally:
                worker.close()


if __name__ == "__main__":
    unittest.main()
