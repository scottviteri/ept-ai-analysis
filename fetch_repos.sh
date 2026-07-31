#!/usr/bin/env bash
# Re-clone the source corpora analyzed in this project (shallow clones).
# Pinned commits below are the exact snapshots used for the July 31, 2026 analysis;
# after cloning you can `git fetch --depth 1 origin <sha> && git checkout <sha>`
# in each repo to reproduce byte-for-byte (if the host still serves those objects).
set -euo pipefail
mkdir -p repos && cd repos

clone () { [ -d "$2" ] || git clone --depth 1 "$1" "$2"; }

clone https://github.com/teorth/pfr.git                                pfr                        # 68730da
clone https://github.com/teorth/equational_theories.git                equational_theories        # 7e276a2
clone https://github.com/ImperialCollegeLondon/FLT.git                 FLT                        # bf70705
clone https://github.com/thefundamentaltheor3m/Sphere-Packing-Lean.git Sphere-Packing-Lean        # 8e1d993
clone https://github.com/math-inc/Sphere-Packing-Lean.git              mathinc-sphere             # 1e98fb4
clone https://github.com/James-Oswald/alphaproof-outputs-mirror.git    alphaproof-outputs-mirror  # f8770a7
clone https://github.com/google-deepmind/alphaproof-nexus-results.git  alphaproof-nexus-results   # 0647711
clone https://github.com/dwrensha/compfiles.git                        compfiles                  # ea08008
clone https://github.com/Lean-zh/IMO_2024.git                          IMO_2024                   # f6b98d1 (note: AlphaProof port, not human)
echo "done."
