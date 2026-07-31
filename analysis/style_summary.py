r"""Aggregate proof-style statistics per corpus."""
import json
import numpy as np

def summarize(path, name):
    S = json.load(open(path))
    if not S:
        print(f"{name}: empty"); return None
    lines = sum(s["n_lines"] for s in S)
    named = sum(s["n_claims"] for s in S)
    anon = sum(s["anon_claims"] for s in S)
    edges = sum(s["n_claim_edges"] for s in S)
    splits = sum(s["case_splits"] for s in S)
    r = {"corpus": name, "n_theorems": len(S), "total_lines": lines,
         "mean_lines_per_thm": round(lines/len(S), 1),
         "named_claims_per_100_lines": round(100*named/lines, 2),
         "anon_claims_per_100_lines": round(100*anon/lines, 2),
         "named_frac": round(named/max(named+anon, 1), 3),
         "claim_edges_per_named": round(edges/max(named, 1), 2),
         "case_splits_per_100_lines": round(100*splits/lines, 2),
         "mean_max_indent": round(float(np.mean([s["max_indent"] for s in S])), 1),
         "max_claim_reuse": max(s["max_claim_reuse"] for s in S)}
    print(json.dumps(r))
    return r

out = []
for p, n in [("graphs/alphaproof_haves.json", "AlphaProof-2024 (IMO, raw)"),
             ("graphs/human_imo_haves.json", "Human IMO 2024 (Myers/mathlib)"),
             ("graphs/nexus_haves.json", "AlphaProof-Nexus 2026 (research)")]:
    out.append(summarize(p, n))
json.dump([o for o in out if o], open("style_summary.json", "w"), indent=1)
