#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=.github/scripts/aps_tools_common.sh
. "$ROOT_DIR/.github/scripts/aps_tools_common.sh"
cd "$ROOT_DIR"

mapfile -t features < <(git ls-files '*.feature' | grep -Ev '(^|/)(\.agents|\.codex|\.gsd|\.skills|skills)/' || true)
if [ "${#features[@]}" -eq 0 ]; then
  echo "No .feature files found; skipping Gherkin mutation gate."
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
