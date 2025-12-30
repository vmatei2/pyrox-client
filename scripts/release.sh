#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <version>"
  echo "Example: $0 0.2.2"
  exit 1
fi

version="$1"
version_file="src/pyrox/__init__.py"

if [[ ! -f "$version_file" ]]; then
  echo "Error: $version_file not found"
  exit 1
fi

python - "$version_file" "$version" <<'PY'
import re
import sys

path = sys.argv[1]
version = sys.argv[2]

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

new_content, count = re.subn(
    r'__version__\s*=\s*"[^"]+"',
    f'__version__ = "{version}"',
    content,
)

if count != 1:
    raise SystemExit("Expected exactly one __version__ assignment to update.")

with open(path, "w", encoding="utf-8") as f:
    f.write(new_content)
PY

git add "$version_file"
git commit -m "Bump version to ${version}"
git tag "v${version}"

cat <<EOF
Tagged v${version} and committed version bump.
Next: git push origin main --tags
EOF
