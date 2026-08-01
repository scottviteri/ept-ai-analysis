r"""Analyze subterm-grain sharing statistics (output of subterm_stats.lean).

The 2019 ManipulateProofTrees question, asked of the ET corpus at kernel
Expr grain: how much *unnamed* internal structure do proofs have, and does it
differ between human constructions and machine-generated certificates?

Per declaration we have: dag (distinct subterms), log10tree (expanded tree
size), edges, shared (subterms referenced >=2 times), maxref, and a sparse
refcount histogram. Derived quantities:

  compression  = log10(tree) - log10(dag)   [orders of magnitude removed
                                             by sharing; the 2019 "cleanup"]
  sharedfrac   = shared / dag               [fraction of DAG that is reused]

We compare strata (SimpleRewrites / Vampire / brute force / All4x4Tables /
MagmaEgg / Greedy vs human Facts, ManuallyProved, framework), overall and
size-matched, and fit the subterm-refcount tail exponent per stratum -- the
2019 paper's alpha, at the 2019 paper's grain, on 2026 data.

usage: python3 analysis/subterm_analysis.py results/et_subterm_stats.jsonl
"""
import json, sys, math, random
from collections import defaultdict, Counter
import numpy as np

sys.path.insert(0, 'analysis')
from analyze import powerlaw_alpha

def stratum(r):
    f, n = r['file'], r['full']
    parts = f.split('.')
    if 'Generated' in parts:
        i = parts.index('Generated')
        m = parts[i + 1] if i + 1 < len(parts) else '?'
        if m in ('SimpleRewrites', 'All4x4Tables', 'VampireProven', 'TrivialBruteforce',
                 'MagmaEgg', 'Greedy', 'EquationSearch', 'FinitePoly'):
            return 'machine:' + m
        return 'machine:other'
    if 'ManuallyProved' in f: return 'human:ManuallyProved'
    if 'Facts' in n: return 'human:Facts'
    if any(x in f for x in ('.Equations', '.Magma', '.MagmaLaw')): return 'framework'
    return 'human:other'

def summarize(rows, label):
    if not rows: return None
    dag = np.array([r['dag'] for r in rows], dtype=float)
    comp = np.array([r['log10tree'] - math.log10(max(r['dag'], 1)) for r in rows])
    sf = np.array([r['shared'] / max(r['dag'], 1) for r in rows])
    mr = np.array([r['maxref'] for r in rows], dtype=float)
    # aggregate refcount tail across the stratum
    hist = Counter()
    for r in rows:
        for k, c in r['h'].items():
            hist[int(k)] += c
    degs = []
    for k, c in hist.items():
        degs += [k] * min(c, 200000)
    a = s = None; nt = None
    if len(degs) > 200:
        a, s, fit = powerlaw_alpha(degs, min_xmin=2)
        nt = fit and fit['ntail']
    rec = {'n': len(rows),
           'dag_median': int(np.median(dag)), 'dag_p90': int(np.percentile(dag, 90)),
           'compression_median': round(float(np.median(comp)), 2),
           'compression_p90': round(float(np.percentile(comp, 90)), 2),
           'sharedfrac_median': round(float(np.median(sf)), 3),
           'maxref_median': int(np.median(mr)),
           'refcount_alpha': a and round(a, 2), 'refcount_alpha_sigma': s and round(s, 2),
           'refcount_ntail': nt}
    print(f"{label:26s} n={rec['n']:6d} dag_med={rec['dag_median']:6d} "
          f"compress_med=10^{rec['compression_median']:<5} sharedfrac={rec['sharedfrac_median']:.3f} "
          f"maxref={rec['maxref_median']:4d} ref_alpha={rec['refcount_alpha']}")
    return rec

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'results/et_subterm_stats.jsonl'
    rows = [json.loads(l) for l in open(path)]
    print(f"{len(rows)} declarations with proof terms\n")
    by = defaultdict(list)
    for r in rows:
        by[stratum(r)].append(r)
    out = {}
    for k in sorted(by):
        out[k] = summarize(by[k], k)

    # size-matched comparison: sample human & machine decls with dag in [100, 3000]
    rng = random.Random(0)
    hum = [r for k, v in by.items() if k.startswith('human') for r in v if 100 <= r['dag'] <= 3000]
    mac = [r for k, v in by.items() if k.startswith('machine') for r in v if 100 <= r['dag'] <= 3000]
    n = min(len(hum), len(mac), 2000)
    print(f"\nsize-matched (dag 100-3000): human n={len(hum)}, machine n={len(mac)}, sampling {n} each")
    out['size_matched'] = {
        'human': summarize(rng.sample(hum, n), 'human (size-matched)'),
        'machine': summarize(rng.sample(mac, n), 'machine (size-matched)')}
    json.dump(out, open('results/et_subterm_summary.json', 'w'), indent=1)
    print('\nsaved results/et_subterm_summary.json')
