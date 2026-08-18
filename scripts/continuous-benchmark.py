from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--runs", type=int, default=2)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update(
        {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONNOUSERSITE": "1", "PYTHONPATH": str(project)}
    )
    process = subprocess.Popen(
        [sys.executable, "-u", "-m", "app.worker"],
        cwd=project,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    assert process.stdin and process.stdout and process.stderr
    threading.Thread(target=lambda: [print(line, end="", file=sys.stderr) for line in process.stderr], daemon=True).start()
    summaries = []
    try:
        for run in range(1, args.runs + 1):
            started = time.perf_counter()
            process.stdin.write(
                json.dumps(
                    {"command": "run", "source": str(args.source.resolve()), "outputDir": str(args.output_dir.resolve())},
                    ensure_ascii=False,
                )
                + "\n"
            )
            process.stdin.flush()
            for line in process.stdout:
                event = json.loads(line)
                print(json.dumps(event, ensure_ascii=False), flush=True)
                if event["event"] == "completed":
                    summaries.append(
                        {
                            "run": run,
                            "externalWallSeconds": time.perf_counter() - started,
                            "output": event["output"],
                            "metrics": event["metrics"],
                        }
                    )
                    break
                if event["event"] == "error":
                    raise RuntimeError(event["message"])
        summary_path = args.output_dir / "continuous-benchmark.json"
        summary_path.write_text(json.dumps({"runs": summaries}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"SUMMARY={summary_path}")
    finally:
        if process.poll() is None:
            process.stdin.write('{"command":"shutdown"}\n')
            process.stdin.flush()
            process.wait(timeout=30)


if __name__ == "__main__":
    main()
