#!/usr/bin/env python3
"""Codex and Claude Code command-hook handler: persist bounded metadata and monotonic timing per turn."""
import fcntl
import hashlib
import json
import os
import re
import sys
import time
import uuid
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'observability'


def safe(value):
    return re.sub(r'[^A-Za-z0-9_.-]', '_', str(value or 'unknown'))[:120]


def main():
    stamp = time.monotonic_ns()
    wall = time.time_ns()
    payload = json.load(sys.stdin)
    event = payload.get('hook_event_name', 'unknown')
    session = safe(payload.get('session_id'))
    turn = safe(payload.get('turn_id'))
    if os.environ.get('ICM_HOOK_RUNTIME') == 'claude':
        session_dir = DATA / session
        session_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (session_dir / '.session.lock').open('a') as session_lock:
            fcntl.flock(session_lock, fcntl.LOCK_EX)
            active = session_dir / '.active_turn'
            if event == 'UserPromptSubmit':
                turn = uuid.uuid4().hex
                active.write_text(turn)
                os.chmod(active, 0o600)
            elif active.exists():
                turn = safe(active.read_text().strip())
    if event == 'SessionStart':
        return
    if turn == 'unknown':
        # Session-wide lifecycle events have no reliable association with a turn.
        return
    directory = DATA / session / turn
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = directory / 'events.jsonl'
        record = {'event': event, 'monotonic_ns': stamp, 'unix_ns': wall}
        for key in ('tool_name', 'tool_use_id', 'model', 'status', 'token_usage', 'trigger', 'agent_id', 'agent_type', 'duration_ms', 'is_interrupt'):
            if key in payload:
                record[key] = payload[key]
        if event in ('PreToolUse', 'PostToolUse', 'PostToolUseFailure'):
            raw = json.dumps(payload.get('tool_input'), sort_keys=True, ensure_ascii=False).encode()
            record['input_bytes'] = len(raw)
            record['input_sha256'] = hashlib.sha256(raw).hexdigest()
            if 'tool_response' in payload:
                response = payload['tool_response']
                record['response_bytes'] = len(json.dumps(response, ensure_ascii=False).encode())
                if isinstance(response, dict):
                    for key in ('exit_code', 'isError'):
                        if key in response:
                            record[key] = response[key]
        with path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
        os.chmod(path, 0o600)
        if event in ('Stop', 'Interrupt'):
            records = [json.loads(line) for line in path.read_text().splitlines()]
            starts = {r.get('tool_use_id'): r for r in records if r['event'] == 'PreToolUse' and r.get('tool_use_id')}
            ends = {r.get('tool_use_id'): r for r in records if r['event'] in ('PostToolUse', 'PostToolUseFailure') and r.get('tool_use_id')}
            calls = []
            for call_id in sorted(starts.keys() | ends.keys()):
                start, end = starts.get(call_id), ends.get(call_id)
                calls.append({'id': call_id, 'tool': (start or end).get('tool_name'),
                              'duration_seconds': (end['monotonic_ns'] - start['monotonic_ns']) / 1e9 if start and end else None,
                              'status': ('failed' if end['event'] == 'PostToolUseFailure' or end.get('isError') is True or (isinstance(end.get('exit_code'), int) and end['exit_code'] != 0) else 'observed_post') if start and end else ('missing_post' if start else 'missing_pre'),
                              'runtime_duration_ms': end.get('duration_ms') if end else None,
                              'exit_code': end.get('exit_code') if end else None,
                              'is_error': end.get('isError') if end else None})
            prompt = next((r for r in records if r['event'] == 'UserPromptSubmit'), None)
            elapsed = (stamp - prompt['monotonic_ns']) / 1e9 if prompt else None
            summary = {'session_id': session, 'turn_id': turn, 'status': 'interrupted' if event == 'Interrupt' else 'stopped',
                       'elapsed_seconds': elapsed,
                       'event_counts': dict(Counter(r['event'] for r in records)), 'tool_calls': calls,
                       'model_requests': [r for r in records if r['event'] == 'PostModelRequest'],
                       'limitations': ['Hook-observed intervals include hook overhead and may omit unsupported tools.', 'Completed means a post hook was observed, not necessarily success.']}
            tmp = directory / 'summary.tmp'
            tmp.write_text(json.dumps(summary, indent=2) + '\n')
            os.chmod(tmp, 0o600)
            tmp.replace(directory / 'summary.json')
            report = [
                '# Hook run report',
                '',
                f"- **Status:** {summary['status']}",
                f"- **Elapsed:** {elapsed:.2f} s" if elapsed is not None else '- **Elapsed:** unavailable',
                f"- **Events:** {sum(summary['event_counts'].values())}",
                '',
                '## Event counts',
                '',
                '| Event | Count |',
                '|---|---:|',
            ]
            report.extend(f'| {name} | {count} |' for name, count in sorted(summary['event_counts'].items()))
            report.extend(['', '## Tool calls', ''])
            if calls:
                report.extend(['| Tool | Status | Duration | Exit code |', '|---|---|---:|---:|'])
                for call in calls:
                    duration = f"{call['duration_seconds']:.2f} s" if call['duration_seconds'] is not None else 'incomplete'
                    exit_code = call['exit_code'] if call['exit_code'] is not None else '—'
                    report.append(f"| {call['tool'] or 'unknown'} | {call['status']} | {duration} | {exit_code} |")
            else:
                report.append('No tool calls were recorded.')
            report.extend(['', '## Model requests', ''])
            if summary['model_requests']:
                report.extend(['| Model | Token usage |', '|---|---|'])
                for request in summary['model_requests']:
                    tokens = json.dumps(request.get('token_usage', {}), ensure_ascii=False) if request.get('token_usage') is not None else 'unavailable'
                    report.append(f"| {request.get('model', 'unknown')} | {tokens} |")
            else:
                report.append('No model request metrics were recorded.')
            report.extend(['', '> Hook timings include hook overhead; a recorded post event does not by itself guarantee the tool succeeded.', ''])
            report_path = directory / 'summary.md'
            report_path.write_text('\n'.join(report), encoding='utf-8')
            os.chmod(report_path, 0o600)
    if event in ('Stop', 'SubagentStop'):
        print('{}')


if __name__ == '__main__':
    main()
