#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

SOURCE="$TMP_DIR/source"
DEST="$TMP_DIR/dest"
LOCK="$TMP_DIR/sources.lock.tsv"

git init --quiet "$SOURCE"
git -C "$SOURCE" config user.name "EPT source-lock test"
git -C "$SOURCE" config user.email "source-lock-test@example.invalid"
mkdir -p "$SOURCE/mizar40"
printf 'pinned\n' > "$SOURCE/value.txt"
printf 'proof data\n' > "$SOURCE/mizar40/atpproved"
git -C "$SOURCE" add value.txt mizar40/atpproved
git -C "$SOURCE" commit --quiet -m "pinned revision"
PINNED=$(git -C "$SOURCE" rev-parse HEAD)

printf 'moving branch\n' > "$SOURCE/value.txt"
git -C "$SOURCE" commit --quiet -am "later revision"

printf 'deepmath\t%s\t%s\n' "$SOURCE" "$PINNED" > "$LOCK"
EPT_REPOS_DIR="$DEST" EPT_SOURCES_LOCK="$LOCK" bash "$ROOT/fetch_repos.sh"

[[ $(git -C "$DEST/deepmath" rev-parse HEAD) == "$PINNED" ]]
[[ $(cat "$DEST/deepmath/value.txt") == "pinned" ]]
[[ -L "$DEST/mizar40" ]]
[[ $(cat "$DEST/mizar40/atpproved") == "proof data" ]]

# A second run must remain pinned even though the source branch moved.
EPT_REPOS_DIR="$DEST" EPT_SOURCES_LOCK="$LOCK" bash "$ROOT/fetch_repos.sh"
[[ $(git -C "$DEST/deepmath" rev-parse HEAD) == "$PINNED" ]]

# Existing tracked work must never be overwritten by the materializer.
printf 'local edit\n' > "$DEST/deepmath/value.txt"
if EPT_REPOS_DIR="$DEST" EPT_SOURCES_LOCK="$LOCK" bash "$ROOT/fetch_repos.sh"; then
  printf 'expected a dirty checkout to be rejected\n' >&2
  exit 1
fi
[[ $(cat "$DEST/deepmath/value.txt") == "local edit" ]]

printf 'source-lock test passed\n'
