# EPT × AI-era mathematics — analysis pipeline

Extends Viteri & DeDeo, *Epistemic phase transitions in mathematical proofs*
(Cognition 225:105120, 2022) to AI-assisted mathematics (2023–2026). Companion
report — with an interactive proof-network + live Ising belief animation — at
**<https://scottviteri.github.io/ept-ai-analysis/>** (source: `report/report.html`).

![PFR kernel-grain dependency network](figs/pfr_network.png)

Analysis date: **2026-07-31**. All inputs are public GitHub repositories,
pinned to the commits listed in `fetch_repos.sh`.

## Layout

```
fetch_repos.sh        clone the 9 source corpora into repos/ (not committed; ~150 MB)
analysis/             the pipeline (pure Python: networkx, numpy, matplotlib)
graphs/               extracted dependency networks (JSON) — the derived dataset
results/              computed metrics + run log
figs/                 report figures (light/dark pairs)
report/               final report (report.html has figures base64-inlined)
```

## Pipeline

1. `extract_blueprint.py <blueprint_dir> <out.json>` — parses leanblueprint LaTeX:
   nodes = statement environments with `\label{}`, edges = author-declared `\uses{}`,
   plus `\lean{}` tags and `\leanok` status. This is the *informal/communication grain*.
2. `extract_lean.py <lean_src_dir> <out.json>` — textual (uncompiled) extraction of
   named declarations and cross-references from Lean 4 sources; namespace-aware,
   unambiguous-suffix matching. This is the *formal/verification grain*.
   **Caveat:** misses tactic-mediated and mathlib-routed edges → edge counts and
   tracking levels are lower bounds; use for cross-corpus comparison.
3. `have_graph.py <files...> <out.json>` — intra-proof claim networks: named vs
   anonymous `have`/`suffices`/`obtain` bindings, claim-reference edges, case-split
   and nesting statistics. Used for AlphaProof-2024 vs human vs Nexus-2026 style.
4. `analyze.py [graph_name]` — per-network battery replicating the 2022 paper:
   degree stats, discrete Clauset–Shalizi–Newman power-law fit (α, xmin by KS),
   modularity (greedy / Louvain above 5k nodes), asymmetric-Ising Glauber belief
   dynamics (p_prior = 0.75, 10 sweeps, β from ε via ε = 1/(1+e^{2β})), f₂ at
   ε = 0.01, and the ΔL₁ modular-firewall statistic (appendix Eq. 2, β = 1).
   Writes `results_all.json`.
5. `et_split.py` — Equational Theories human stratum vs `Generated/` machine
   stratum comparison, incl. per-generation-method internal edge density.
6. `sphere_compare.py` — human-led vs Math Inc (Gauss-completed) sphere packing
   repos; declaration-name survival; Dim24 pure-AI subtree.
7. `track.py` — tracking fidelity (DeDeo & Duede's correspondence condition):
   fraction of blueprint edges realized as paths (≤6 hops) between `\lean{}`-tagged
   declarations. Writes `tracking_results.json`.
8. `style_summary.py`, `gen_figures.py` — aggregate tables and figures.

## Reproduce

```bash
python3 -m pip install networkx numpy matplotlib   # scipy optional
bash fetch_repos.sh
# re-extract graphs (or use the committed graphs/*.json snapshots directly):
python3 analysis/extract_blueprint.py repos/pfr/blueprint graphs/pfr_blueprint.json
python3 analysis/extract_lean.py repos/pfr/PFR graphs/pfr_lean.json
# ... (same pattern for FLT, Sphere-Packing-Lean, mathinc-sphere, equational_theories)
python3 analysis/analyze.py            # ~10 min; et_lean dominates
python3 analysis/et_split.py
python3 analysis/sphere_compare.py
python3 analysis/track.py
python3 analysis/have_graph.py repos/alphaproof-outputs-mirror/originals/P{1,2,6}.lean graphs/alphaproof_haves.json
python3 analysis/have_graph.py repos/compfiles/Compfiles/Imo2024P{1,2,6}.lean graphs/human_imo_haves.json
python3 analysis/have_graph.py $(find repos/alphaproof-nexus-results -name '*.lean' ! -name 'lakefile*') graphs/nexus_haves.json
python3 analysis/style_summary.py
mkdir -p figs && python3 analysis/gen_figures.py
```

The committed `graphs/*.json` are the exact extractions behind `results/` and the
report, so every downstream number is reproducible without network access.

## Kernel-grain validation (added after initial release)

Textual extraction was validated against ground truth for PFR: the project was
built (`lake exe cache get && lake build`), and `analysis/extract_deps.lean`
loads the compiled environment and records, per project-internal constant, the
constants its type and proof term actually use (`Expr.getUsedConstants`).
Two Lean 4.33 gotchas encoded there: module-system private olean parts require
per-module `importAll := true`, and `ConstantInfo.value?` returns theorem
proofs only with `(allowOpaque := true)`.

Run (zsh-safe; from `repos/pfr` after building):
```bash
(cd .lake/build/lib/lean && find PFR -name '*.olean' | sed 's/\.olean$//' |   while read m; do if [ -f "$m.olean.private" ]; then echo "+${m//\//.}";   else echo "${m//\//.}"; fi; done; echo "+PFR") |   xargs lake env lean --run ../../analysis/extract_deps.lean PFR > kernel_deps.jsonl
python3 ../../analysis/kernel_compare.py kernel_deps.jsonl ../../graphs/pfr_lean.json ../../graphs/pfr_kernel.json
```

Results (`results/pfr_kernel_deps.jsonl`, `graphs/pfr_kernel.json`):
| metric | kernel grain | textual grain |
|---|---|---|
| N / E (LWCC) | 1304 / 5607 | 1011 / 2690 |
| α (out-degree) | 2.46 ± 0.23 | 2.27 ± 0.22 |
| modularity Q | 0.55 | 0.59 |
| tracking: blueprint edges realized (≤6 hops) | **86%** | 74% |

Textual edge precision vs kernel truth: 0.895; recall 0.531 (missing edges are
instance resolution, notation, and tactic-mediated uses). Conclusion: textual
graphs are a high-precision subsample; α/Q conclusions are robust; tracking
levels are lower bounds (gradient unchanged). PFR declarations make 88,790
distinct references into mathlib/core (~68 per declaration).

## Headline numbers

| finding | value |
|---|---|
| α, human-led Lean 2023–26 (PFR / FLT / Sphere / ET-human) | 2.26 / 2.33 / 1.98 / 2.08 |
| α, Gauss AI-completed sphere (whole / pure-AI Dim24) | 1.94 / 2.10 |
| α, blueprints (PFR / FLT / Sphere / ET) | 3.43 / 3.28 / 4.64 / 2.41 |
| ET machine stratum | 11,568 fragments; 0 internal edges in top-4 methods; no power law |
| ET cross-strata edges (human→machine / machine→human) | 31,776 / 619 |
| Named-claim density per 100 lines (AlphaProof-2024 / human / Nexus-2026) | 0.0 / 5.1 / 17.7 |
| Tracking fidelity (PFR / Sphere / FLT / ET) | 74% / 51% / 47% / 37% |
| f₂ at ε = 0.01, ΔL₁ | 0.85–1.0, +2.8…+9.8 (EPTs and firewalls persist everywhere connected) |
