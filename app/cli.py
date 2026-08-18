from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from .config import PROJECT_ROOT, runtime_python
from .i18n import tr


def run_worker(command: dict[str, object], fake: bool = False) -> int:
    environment = os.environ.copy()
    environment.update(
        {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONNOUSERSITE": "1", "PYTHONPATH": str(PROJECT_ROOT)}
    )
    if fake:
        environment["SEEDVR2_FAKE"] = "1"
    process = subprocess.Popen(
        [str(runtime_python()), "-u", "-m", "app.worker"],
        cwd=PROJECT_ROOT,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert process.stdin and process.stdout
    assert process.stderr
    threading.Thread(target=lambda: [print(line, end="", file=sys.stderr) for line in process.stderr], daemon=True).start()
    process.stdin.write(json.dumps(command, ensure_ascii=False) + "\n")
    process.stdin.flush()
    exit_code = 1
    success_events = {"self_check"} if command.get("command") == "self_check" else {"completed"}
    for line in process.stdout:
        event = json.loads(line)
        print(json.dumps(event, ensure_ascii=False), flush=True)
        if event["event"] in success_events:
            exit_code = 0
            break
        if event["event"] in {"error", "cancelled"}:
            break
    process.stdin.write('{"command":"shutdown"}\n')
    process.stdin.flush()
    process.wait(timeout=30)
    return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(description=tr("cli.description"))
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--cuda", action="store_true")
    run = sub.add_parser("run")
    run.add_argument("source", type=Path)
    run.add_argument("output_dir", type=Path)
    run.add_argument("--fake", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.command == "check":
        raise SystemExit(run_worker({"command": "self_check", "withCuda": args.cuda}))
    raise SystemExit(
        run_worker(
            {"command": "run", "source": str(args.source.resolve()), "outputDir": str(args.output_dir.resolve())},
            fake=args.fake,
        )
    )


if __name__ == "__main__":
    main()
