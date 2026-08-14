#!/usr/bin/env bash
# Materialize the exact source snapshots used by the analysis.
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
LOCK_FILE=${EPT_SOURCES_LOCK:-"$SCRIPT_DIR/sources.lock.tsv"}
REPOS_DIR=${EPT_REPOS_DIR:-"$SCRIPT_DIR/repos"}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

checkout_locked_source() {
  local directory=$1
  local url=$2
  local commit=$3
  local target="$REPOS_DIR/$directory"
  local actual

  [[ $commit =~ ^[0-9a-f]{40}$ ]] || die "$directory has a non-full commit SHA: $commit"

  if [[ -e $target && ! -d $target/.git ]]; then
    die "$target exists but is not a Git checkout"
  fi

  if [[ ! -d $target/.git ]]; then
    mkdir -p "$target"
    git -C "$target" init --quiet
    git -C "$target" remote add origin "$url"
  fi

  if ! git -C "$target" diff --quiet || ! git -C "$target" diff --cached --quiet; then
    die "$target has tracked changes; refusing to change its revision"
  fi

  # Fetch from the locked URL directly. Existing checkouts may use an SSH
  # origin, and reproducing the analysis should not rewrite a user's remotes.
  git -C "$target" fetch --quiet --depth 1 "$url" "$commit"
  git -C "$target" checkout --quiet --detach FETCH_HEAD
  actual=$(git -C "$target" rev-parse HEAD)
  [[ $actual == "$commit" ]] || die "$directory resolved to $actual, expected $commit"
  printf '%-28s %s\n' "$directory" "$actual"
}

prepare_mizar40_path() {
  local source="$REPOS_DIR/deepmath/mizar40"
  local compatibility_path="$REPOS_DIR/mizar40"

  [[ -d $source ]] || return 0
  if [[ -L $compatibility_path ]]; then
    [[ $(readlink "$compatibility_path") == "deepmath/mizar40" ]] ||
      die "$compatibility_path is a symlink to an unexpected target"
  elif [[ -e $compatibility_path ]]; then
    diff --quiet --recursive "$source" "$compatibility_path" ||
      die "$compatibility_path differs from the pinned deepmath/mizar40 tree"
  else
    ln -s "deepmath/mizar40" "$compatibility_path"
  fi
}

[[ -f $LOCK_FILE ]] || die "source lock not found: $LOCK_FILE"
mkdir -p "$REPOS_DIR"

count=0
while IFS=$'\t' read -r directory url commit; do
  [[ -z ${directory//[[:space:]]/} || $directory == \#* ]] && continue
  [[ -n $url && -n $commit ]] || die "malformed source-lock row for $directory"
  checkout_locked_source "$directory" "$url" "$commit"
  count=$((count + 1))
done < "$LOCK_FILE"

prepare_mizar40_path
printf 'verified %d locked source snapshots in %s\n' "$count" "$REPOS_DIR"
