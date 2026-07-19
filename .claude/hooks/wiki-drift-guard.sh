#!/bin/bash
# Stop-hook drift guard: when code files are dirty but wiki/ is untouched,
# remind the agent once per change-set to run the /wiki sync workflow.
# Fires at most once per distinct dirty-file set per session (marker file),
# so an explicit "no wiki impact" answer is not re-nagged.

input=$(cat)
session_id=$(printf '%s' "$input" | jq -r '.session_id // "nosession"' 2>/dev/null)
[ -z "$session_id" ] && session_id="nosession"

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$repo_root" || exit 0

code_paths='^(src/|pyrox_api_service/|ui/src/|tests/|scripts/|\.github/workflows/|Dockerfile|fly\.toml|pyproject\.toml)'

status=$(git status --porcelain 2>/dev/null) || exit 0
dirty=$(printf '%s\n' "$status" | awk '{print $2}' | grep -v '\.DS_Store' | grep -E "$code_paths" | sort)
[ -z "$dirty" ] && exit 0

wiki_dirty=$(printf '%s\n' "$status" | awk '{print $2}' | grep -E '^wiki/' | head -1)
[ -n "$wiki_dirty" ] && exit 0

marker="${TMPDIR:-/tmp}/claude-wiki-drift-${session_id}"
current_hash=$(printf '%s' "$dirty" | shasum | cut -d' ' -f1)
if [ -f "$marker" ] && [ "$(cat "$marker")" = "$current_hash" ]; then
  exit 0
fi
printf '%s' "$current_hash" > "$marker"

files_list=$(printf '%s' "$dirty" | tr '\n' ' ')
cat <<EOF
{"decision": "block", "reason": "Wiki drift guard: code changed but wiki/ was not updated (dirty: ${files_list}). Per the Wiki section of CLAUDE.md: grep these paths against the 'sources:' frontmatter in wiki/*.md, update the affected pages, and append a sync entry to wiki/log.md. If the change genuinely has no wiki impact, say so in your summary and finish - this reminder will not repeat for the same change-set."}
EOF
exit 0
