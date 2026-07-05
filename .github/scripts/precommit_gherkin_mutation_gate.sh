#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=.github/scripts/aps_tools_common.sh
. "$ROOT_DIR/.github/scripts/aps_tools_common.sh"
cd "$ROOT_DIR"

CHUNK_INDEX=0
TOTAL_CHUNKS=1

while [[ $# -gt 0 ]]; do
  case $1 in
    --chunk)
      CHUNK_INDEX="$2"
      shift 2
      ;;
    --total-chunks)
      TOTAL_CHUNKS="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

mapfile -t all_features < <(git ls-files '*.feature' | grep -Ev '(^|/)(\.agents|\.codex|\.gsd|\.skills|skills)/' || true)

features=()
for i in "${!all_features[@]}"; do
  if [ $(( i % TOTAL_CHUNKS )) -eq "$CHUNK_INDEX" ]; then
    features+=("${all_features[$i]}")
  fi
done

if [ "${#features[@]}" -eq 0 ]; then
  echo "No .feature files found in this chunk; skipping Gherkin mutation gate."
  exit 0
fi

runner="${GHERKIN_MUTATION_RUNNER:-.github/scripts/run_acceptance_mutation_worker.sh}"

ensure_aps_tools gherkin-mutator

if [ ! -x "$runner" ]; then
  echo "Feature files exist, but $runner is missing or not executable." >&2
  echo "Add a project-specific APS mutation runner worker before enabling Gherkin mutation." >&2
  exit 1
fi

mkdir -p build/acceptance-mutation
for feature in "${features[@]}"; do
  slug="${feature//\//__}"
  slug="${slug// /__}"
  work_dir="build/acceptance-mutation/${slug%.feature}"
  mkdir -p "$work_dir"
  feature_copy="$work_dir/${feature##*/}"
  cp "$feature" "$feature_copy"
  gherkin-mutator \
    --feature "$feature_copy" \
    --runner-worker "./$runner" \
    --level soft \
    --work-dir "$work_dir" \
    --json > "$work_dir/report.json"
done
