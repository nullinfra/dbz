#!/usr/bin/env python3
"""01_spawn: run one `codex exec` per case, in parallel (gpt-6-luna, medium effort).

Usage: python3 geolocation_evals/_factory/tools/run_codex.py <eval_id> [--jobs 36] [--model gpt-6-luna] [--effort medium]
Run from the maps/ workspace root. Does not retry failed cases.
"""
import argparse, json, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # maps/


def run_case(case_dir: Path, model: str, effort: str, timeout: int) -> tuple[str, int]:
    prompt = (case_dir / "prompt.md").read_text()
    cmd = [
        "codex", "exec", "--skip-git-repo-check", "--ephemeral", "--trust", "--dangerously-bypass-hook-trust",
        "-m", model, "-c", f'model_reasoning_effort="{effort}"',
        "-s", "workspace-write", "-c", "sandbox_workspace_write.network_access=true", "-C", str(case_dir / "workspace"),
        "-o", str(case_dir / "codex_last_message.md"),
        "-",
    ]
    with open(case_dir / "codex.log", "w") as log:
        try:
            p = subprocess.run(cmd, input=prompt, text=True, stdout=log,
                               stderr=subprocess.STDOUT, timeout=timeout)
            return case_dir.name, p.returncode
        except subprocess.TimeoutExpired:
            return case_dir.name, -1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("eval_id")
    ap.add_argument("--jobs", type=int, default=36)
    ap.add_argument("--model", default="gpt-6-luna")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--timeout", type=int, default=1200)
    a = ap.parse_args()

    eval_dir = ROOT / "geolocation_evals" / "results" / a.eval_id
    cases = [eval_dir / "cases" / c["dir"] for c in json.loads((eval_dir / "eval.json").read_text())["cases"]]
    t0 = time.time()
    failed = []
    with ThreadPoolExecutor(a.jobs) as ex:
        for name, rc in ex.map(lambda c: run_case(c, a.model, a.effort, a.timeout), cases):
            print(f"{'ok  ' if rc == 0 else 'FAIL'} {name} (rc={rc})", flush=True)
            if rc != 0:
                failed.append(name)
    print(f"done {len(cases) - len(failed)}/{len(cases)} in {time.time() - t0:.0f}s")
    sys.exit(0)  # failed cases are scored as-is; no retries


if __name__ == "__main__":
    main()
