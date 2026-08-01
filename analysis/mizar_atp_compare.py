r"""Search-generated proofs on a general library: Mizar humans vs Vampire/E.

Answers the question left open by the ET parallel-task confound: on
mathematics NOT selected for parallelizability, does search-based proving
show the same reuse structure as human proving?

Data (both public):
 - JUrban/MPTP2078 bushy/: 2078 theorems (33 Mizar articles up to
   Bolzano-Weierstrass); each problem's axioms = the HUMAN Mizar proof's
   dependencies (MPTP-computed).
 - JUrban/deepmath mizar40/atpproved: 32,524 MML theorems ATP-proved in the
   Mizar40 experiments; each line lists the premises used in the minimized
   ATP (Vampire/E) proof.
Matched set: 1,274 theorems with both a human and an ATP proof.

Method: build premise-usage networks (premise -> theorem edges) for both
provers over the same theorems; drop MPTP background axioms (present in >30%
of problems); compare mean premises/proof, reuse concentration (Gini,
CSN alpha), hub identity, per-theorem premise containment; control for the
ATP's smaller proofs by subsampling human dep-lists to ATP sizes (20 reps).

Findings (results/mizar_atp_compare.json):
 - ATP proofs are 3x leaner (5.1 vs 16.5 premises) and heavily rerouted:
   only 29% of ATP premises appear in the human dependency set.
 - Human reuse: alpha=2.36+-0.09 (ntail=248), Gini=0.740. ATP reuse:
   alpha=3.18+-0.38 (ntail=33), Gini=0.567 - flatter, hub-deficient.
 - Size-matched control: subsampled human Gini=0.669+-0.002, still well
   above ATP's 0.567; the concentration gap is not a proof-size artifact.
 - Note: Mizar40 premise selection was kNN-trained on human proofs, biasing
   the ATP TOWARD human routes; unbiased search would diverge further.

usage: python3 analysis/mizar_atp_compare.py  (expects repos/MPTP2078,
       repos/mizar40; writes results/mizar_atp_compare.json)
"""
import os, re, json, random
from collections import Counter
import numpy as np
import sys
sys.path.insert(0, 'analysis')
from analyze import powerlaw_alpha

bushy = {}
for fn in os.listdir('repos/MPTP2078/bushy'):
    thm = fn.split('__')[1][:-2]
    bushy[thm] = [m.group(1) for line in open(f'repos/MPTP2078/bushy/{fn}')
                  if (m := re.match(r'fof\((\w+), axiom', line))]
atp = {}
for line in open('repos/mizar40/atpproved'):
    name, _, rest = line.partition(':')
    atp[name] = rest.split()
shared = sorted(set(bushy) & set(atp))
cnt = Counter()
for t in shared:
    for d in set(bushy[t]): cnt[d] += 1
bg = {d for d, c in cnt.items() if c > 0.3 * len(shared)}

def stats(usage):
    nd = [len(v) for v in usage.values()]
    reuse = Counter()
    for v in usage.values():
        for d in set(v): reuse[d] += 1
    degs = list(reuse.values())
    a, s, fit = powerlaw_alpha(degs)
    ds = np.sort(degs)
    gini = float((2*np.arange(1, len(ds)+1) - len(ds) - 1).dot(ds) / (len(ds) * ds.sum()))
    return {'mean_deps': round(float(np.mean(nd)), 1), 'n_premises': len(reuse),
            'alpha': a and round(a, 2), 'alpha_sigma': s and round(s, 2),
            'ntail': fit and fit['ntail'], 'gini': round(gini, 3),
            'top10': [x for x, _ in reuse.most_common(10)]}, reuse

hu, hr = stats({t: [d for d in bushy[t] if d not in bg] for t in shared})
ma, mr = stats({t: [d for d in atp[t] if d not in bg] for t in shared})
cont = [len((set(atp[t]) - bg) & (set(bushy[t]) - bg)) / len(set(atp[t]) - bg)
        for t in shared if set(atp[t]) - bg]
rng = random.Random(0)
ginis = []
for rep in range(20):
    reuse = Counter()
    for t in shared:
        h = [d for d in bushy[t] if d not in bg]
        k = min(len(h), len([d for d in atp[t] if d not in bg]))
        for d in (rng.sample(h, k) if k < len(h) else h): reuse[d] += 1
    ds = np.sort(list(reuse.values()))
    ginis.append(float((2*np.arange(1, len(ds)+1) - len(ds) - 1).dot(ds) / (len(ds) * ds.sum())))
out = {'matched_theorems': len(shared), 'background_removed': len(bg),
       'human': hu, 'atp': ma,
       'atp_premise_containment_in_human': round(float(np.mean(cont)), 3),
       'top50_hub_overlap': len({k for k, _ in hr.most_common(50)} & {k for k, _ in mr.most_common(50)}),
       'human_size_matched_gini': [round(float(np.mean(ginis)), 3), round(float(np.std(ginis)), 3)]}
json.dump(out, open('results/mizar_atp_compare.json', 'w'), indent=1)
print(json.dumps(out, indent=1))
