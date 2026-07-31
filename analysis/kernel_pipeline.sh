#!/usr/bin/env bash
# Kernel-grain extraction cycle for one project.
# usage: bash analysis/kernel_pipeline.sh <repo_subdir> <olean_root> <root_module> <textual_graph> <blueprint_graph|-> <prefix>
# e.g.:  bash analysis/kernel_pipeline.sh FLT FLT FLT flt_lean.json flt_blueprint.json flt
# Run from the ept-ai-analysis root. Builds the project (mathlib via cache),
# extracts the kernel dependency graph, compares against the textual graph,
# recomputes tracking fidelity, and saves everything under results/ and graphs/.
# Does NOT delete the build; clearing is a separate explicit step.
set -euo pipefail
REPO="repos/$1"; OROOT="$2"; RMOD="$3"; TEXTUAL="graphs/$4"; BP="$5"; PREFIX="$6"
ROOTDIR="$(pwd)"

echo "=== [$PREFIX] cache get + build ($(date +%H:%M)) ==="
( cd "$REPO"
  lake exe cache get 2>&1 | tail -2
  lake build 2>&1 | tail -3 )

echo "=== [$PREFIX] extract kernel graph ==="
LIBDIR="$REPO/.lake/build/lib/lean"
[ -d "$LIBDIR" ] || LIBDIR="$REPO/.lake/build/lib"
# module list; "+" marks modules with private olean parts (module system)
MODLIST=$(cd "$LIBDIR" && { find "$OROOT" -name '*.olean' | sed 's/\.olean$//' | \
  while read -r m; do
    if [ -f "$m.olean.private" ]; then echo "+${m//\//.}"; else echo "${m//\//.}"; fi
  done
  if [ -f "$OROOT.olean" ]; then
    if [ -f "$OROOT.olean.private" ]; then echo "+$OROOT"; else echo "$OROOT"; fi
  fi; })
if echo "$MODLIST" | grep -q '^+'; then SCRIPT="extract_deps.lean"; else SCRIPT="extract_deps_legacy.lean"; fi
echo "using $SCRIPT ($(echo "$MODLIST" | wc -l) modules, $(echo "$MODLIST" | grep -c '^+' || true) with private parts)"
( cd "$REPO" && echo "$MODLIST" | xargs lake env lean --run "$ROOTDIR/analysis/$SCRIPT" "$RMOD" ) \
  > "results/${PREFIX}_kernel_deps.jsonl" 2> "results/${PREFIX}_kernel_extract.log"
tail -1 "results/${PREFIX}_kernel_extract.log"

echo "=== [$PREFIX] compare vs textual + tracking ==="
{ python3 analysis/kernel_compare.py "results/${PREFIX}_kernel_deps.jsonl" "$TEXTUAL" "graphs/${PREFIX}_kernel.json"
  if [ "$BP" != "-" ]; then
    echo "--- tracking (kernel grain) ---"
    python3 -c "
import sys; sys.path.insert(0,'analysis')
from track import main
main('graphs/$BP', 'graphs/${PREFIX}_kernel.json', '${PREFIX}-kernel')"
  fi
} | tee "results/${PREFIX}_kernel_validation.txt"
echo "=== [$PREFIX] done; saved results/${PREFIX}_kernel_deps.jsonl, graphs/${PREFIX}_kernel.json, results/${PREFIX}_kernel_validation.txt ==="
df -h / | tail -1
