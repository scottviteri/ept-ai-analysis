r"""The parallel-task confound, tested.

Objection (S.V.): the ET machine stratum's dust structure may be a property of
the *task* — the magma-implication problem was chosen for parallelizability —
rather than of search-based proving. Test: compare construction-specific
transitive proof support (project-internal ancestors, excluding equation
definitions and mass-cited framework, i.e. decls cited by >300 results) for
result-theorems of the same task, split by author and instance type.

Finding: the easy mass is flat for everyone (human ordinary implications
median support 1, same as machine search certificates); the deep instances
(human counterexample Facts, median 33, max 53) exist within the same task and
were reached only by constructed mathematics (human, or human-designed
frameworks machine-instantiated: Greedy tail to 31). Search harvested exactly
the stratum where dust suffices.

usage: python3 analysis/et_depth_split.py   (writes results/et_depth_split.json)
"""
import json, re, random
from collections import defaultdict, deque, Counter
import numpy as np

rows = [json.loads(l) for l in open('results/et_kernel_deps.jsonl')]
deps_of = {r['full']: [d for d in r['deps'] if d != r['full']] for r in rows}
eqdef_re = re.compile(r'^(Equation|Law)\d+(\.|$)')
cited = Counter()
for r in rows:
    for d in set(r['deps']): cited[d] += 1
generic = {d for d, c in cited.items() if c > 300}

def specific_support(name, cap=100000):
    seen = set(); q = deque(deps_of.get(name, []))
    while q and len(seen) < cap:
        x = q.popleft()
        if x in seen or eqdef_re.match(x) or x in generic: continue
        seen.add(x)
        q.extend(deps_of.get(x, []))
    return len(seen)

impl_re = re.compile(r'(^|\.)(Equation|Law)\d+_implies_(Equation|Law)\d+$')
cats = defaultdict(list)
for r in rows:
    if r['kind'] != 'theorem': continue
    n, f = r['full'], r['file']
    if impl_re.search(n):
        if any(m in f for m in ('.Generated.SimpleRewrites', '.Generated.All4x4Tables',
                                 '.Generated.VampireProven', '.Generated.TrivialBruteforce')):
            cats['machine-search impl'].append(n)
        elif any(m in f for m in ('.Generated.Greedy', '.Generated.MagmaEgg', '.Generated.EquationSearch')):
            cats['machine framework-instantiated impl'].append(n)
        elif '.Generated.' in f: cats['machine other impl'].append(n)
        elif 'ManuallyProved' in f: cats['human hard impl (ManuallyProved)'].append(n)
        else: cats['human other impl'].append(n)
    elif 'Facts' in n:
        if '.Generated.' in f: cats['machine Facts'].append(n)
        else: cats['human Facts (counterexamples)'].append(n)

rng = random.Random(0)
out = {}
for cat, names in sorted(cats.items()):
    sample = names if len(names) <= 400 else rng.sample(names, 400)
    sizes = [specific_support(x) for x in sample]
    out[cat] = {'n': len(names), 'median': int(np.median(sizes)),
                'mean': round(float(np.mean(sizes)), 1),
                'p90': int(np.percentile(sizes, 90)), 'max': int(max(sizes))}
    print(cat, out[cat])
json.dump(out, open('results/et_depth_split.json', 'w'), indent=1)
print('saved results/et_depth_split.json')
