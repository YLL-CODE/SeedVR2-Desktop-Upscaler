from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from typing import Any

from .config import PROJECT_ROOT, runtime_python
from .i18n import tr


class WorkerClient:
    def __init__(self, events: queue.Queue[dict[str, Any]], language: str) -> None:
        environment = os.environ.copy()
        environment.update(
            {
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONNOUSERSITE": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(PROJECT_ROOT),
                "SEEDVR2_LANGUAGE": language,
            }
        )
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self.process = subprocess.Popen(
            [str(runtime_python()), "-B", "-u", "-m", "app.worker"],
            cwd=PROJECT_ROOT,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            creationflags=flags,
        )
        self.events = events
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self) -> None:
        assert self.process.stdout
        for line in self.process.stdout:
            try:
                self.events.put(json.loads(line))
            except json.JSONDecodeError:
                self.events.put({"event": "error", "message": tr("worker.protocol_broken"), "detail": line})
        code = self.process.poll()
        if code not in (None, 0):
            self.events.put({"event": "error", "message": tr("worker.exited", code=code)})

    def _read_stderr(self) -> None:
        assert self.process.stderr
        for line in self.process.stderr:
            self.events.put({"event": "worker_log", "message": line.rstrip()})

    def send(self, command: dict[str, Any]) -> None:
        if self.process.poll() is not None or not self.process.stdin:
            raise RuntimeError(tr("worker.not_running"))
        self.process.stdin.write(json.dumps(command, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def close(self) -> None:
        if self.process.poll() is not None:
            return
        try:
            self.send({"command": "shutdown"})
            self.process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            self.process.terminate()
