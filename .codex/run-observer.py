#!/usr/bin/env python3
"""Cross-platform Codex hook observer wrapper."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def main() -> int:
    if os.environ.get("ICM_DISABLE_OBSERVABILITY") == "1":
        return 0

    root = Path(__file__).resolve().parents[1]
    maps_root = root / "maps"
    runs = maps_root / "output" / "runs"
    state_root = Path(tempfile.gettempdir()) / "icm-observability"
    runs.mkdir(parents=True, exist_ok=True)
    state_root.mkdir(parents=True, exist_ok=True)

    payload = sys.stdin.read()
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    active_file = state_root / ".active-run"

    if event == "UserPromptSubmit" or not active_file.is_file():
        stamp = datetime.now(ZoneInfo("Europe/Lisbon")).strftime("%Y%m%d-%H%M%S")
        run_dir = runs / stamp
        try:
            run_dir.mkdir(parents=False, exist_ok=False)
        except FileExistsError:
            stamp = f"{stamp}-{os.getpid()}"
            run_dir = runs / stamp
            run_dir.mkdir(parents=True, exist_ok=True)
        active_file.write_text(stamp + "\n", encoding="utf-8")
    else:
        stamp = active_file.read_text(encoding="utf-8").strip()
        if not stamp or re.search(r"[^0-9-]", stamp):
            return 1
        run_dir = runs / stamp
        run_dir.mkdir(parents=True, exist_ok=True)

    obs_dir = state_root / stamp
    obs_dir.mkdir(parents=True, exist_ok=True)

    env = {**os.environ, "ICM_OBSERVABILITY_DIR": str(obs_dir)}
    obs_script = maps_root / "geolocation_icm" / "_config" / "observe.py"
    subprocess.run([sys.executable, str(obs_script)], input=payload, text=True, env=env, check=True)

    event_files = list(obs_dir.rglob("events.jsonl"))
    if event_files:
        latest = max(event_files, key=lambda p: p.stat().st_mtime_ns)
        logdir = latest.parent
        summary_json = logdir / "summary.json"
        summary_md = logdir / "summary.md"
        if summary_json.is_file() and summary_md.is_file():
            enrich = root / ".codex" / "enrich-observer.cjs"
            subprocess.run(["node", str(enrich), str(logdir)], check=True)
            shutil.copyfile(summary_md, run_dir / "summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
