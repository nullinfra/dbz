# 01_spawn — run each conversation in its own session

## Inputs

- Frozen manifest in the [preparation working directory](../00_prepare/CONTEXT.md#outputs).
- The [normal OlaClick router](../../../CONTEXT.md) and its tools.

## Process

```sh
node ola_click/ola_click_evals/_factory/tools/run.cjs "$eval_dir"
```

The runner starts a local HTTPS fixture and confirms that the normal executor can reach it before launching any workers. It auto-detects whether it is running from Codex or Claude (`--runner auto|codex|claude`): Codex runs cases concurrently in batches of 10, while Claude runs cases concurrently in batches of 50 as isolated subagent sessions. Each case gets independent state and a cold session; the next turn resumes that session with only its own verbatim message, verified actor and output path. Turns within a case run in order. An interrupted turn ends that conversation and still triggers fixture cleanup.

## Outputs

The temporary working directory holds each turn's message, blind prompt, Codex events, reply and OlaClick artifacts under `cases/<case>/<turn>/`. Each case's `execution.json` records tool calls, per-turn menu snapshots, and the initial, final and post-cleanup menu. The runner records the execution state in the working directory's `status.json`.

## Check

Inspect `status.json` and failed worker logs if needed. Run [02_score](../02_score/CONTEXT.md) even when execution fails so missing turns and failed writes appear in the report.
