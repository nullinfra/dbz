#!/bin/sh
set -eu
if [ "${ICM_DISABLE_OBSERVABILITY:-0}" = "1" ]; then
  exit 0
fi
case "$PWD" in
  */geolocation_icm) root=$(dirname "$PWD") ;;
  *) root=$PWD ;;
esac
runs="$root/output/runs"
state_root="/tmp/icm-observability"
mkdir -p "$runs" "$state_root"
input=$(mktemp)
trap 'rm -f "$input"' EXIT
cat > "$input"
event=${1:-}
active_file="$state_root/.active-run"
if [ "$event" = UserPromptSubmit ] || [ ! -f "$active_file" ]; then
  stamp=$(TZ=Europe/Lisbon date +%Y%m%d-%H%M%S)
  run="$runs/$stamp"
  if ! mkdir "$run" 2>/dev/null; then
    stamp=$(TZ=Europe/Lisbon date +%Y%m%d-%H%M%S)-$$
    run="$runs/$stamp"
    mkdir "$run"
  fi
  printf '%s\n' "$stamp" > "$active_file"
else
  stamp=$(cat "$active_file")
  case "$stamp" in *[!0-9-]*|'') exit 1 ;; esac
  run="$runs/$stamp"
  mkdir -p "$run"
fi
obs_dir="$state_root/$stamp"
mkdir -p "$obs_dir"
ICM_OBSERVABILITY_DIR="$obs_dir" python3 "$root/geolocation_icm/_config/observe.py" < "$input"
events=$(find "$obs_dir" -name events.jsonl -type f -printf '%T@ %p\n' | sort -rn | head -1 | cut -d' ' -f2-)
if [ -n "$events" ]; then
  logdir=$(dirname "$events")
  if [ -f "$logdir/summary.json" ] && [ -f "$logdir/summary.md" ]; then
    node "$root/.codex/enrich-observer.cjs" "$logdir"
    cp "$logdir/summary.md" "$run/summary.md"
  fi
fi
