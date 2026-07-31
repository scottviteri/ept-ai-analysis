"""What does an unfinished proof do to the Ising belief model?

Runs Glauber dynamics on a kernel graph twice:
 (a) baseline — sorried nodes are ordinary spins (they already have weak
     support: their proof term is just sorryAx, so they sit near-leaf);
 (b) clamped — sorried nodes held at -1 (community disbelieves the gap).
Reports equilibrium belief for three classes: direct-sorry, downstream of a
sorry (tainted), and clean — at strong coupling (eps=0.01, post-EPT) and
near-critical (eps=0.2).

usage: python3 analysis/sorry_ising.py <prefix> <kernel_graph.json> <kernel_deps.jsonl>
"""
import json, sys, math
import numpy as np
from collections import defaultdict, deque

sys.path.insert(0, 'analysis')

def main(prefix, gpath, jsonl):
    g = json.load(open(gpath))
    names = [d["full"] for d in g["decls"]]
    idx = {n: i for i, n in enumerate(names)}
    N = len(names)
    parents = [[] for _ in range(N)]   # deps of i (its proof's supports)
    children = [[] for _ in range(N)]  # users of i
    for u, v in g["edges"]:            # u is dep of v (u used by v)
        parents[v].append(u)
        children[u].append(v)

    rows = [json.loads(l) for l in open(jsonl)]
    direct = {r["full"] for r in rows if "sorryAx" in r.get("ext_deps", [])}
    users = defaultdict(list)
    for r in rows:
        for d in r["deps"]:
            if d != r["full"]:
                users[d].append(r["full"])
    tainted = set(direct); q = deque(direct)
    while q:
        x = q.popleft()
        for u in users[x]:
            if u not in tainted:
                tainted.add(u); q.append(u)

    cls = np.zeros(N, dtype=int)  # 0 clean, 1 downstream, 2 direct
    for n in tainted:
        if n in idx: cls[idx[n]] = 1
    for n in direct:
        if n in idx: cls[idx[n]] = 2
    clamp = np.where(cls == 2)[0]

    def run(eps, clamp_set, seed):
        beta = 0.5 * math.log((1 - eps) / eps)
        rng = np.random.default_rng(seed)
        s = np.where(rng.random(N) < 0.75, 1, -1).astype(np.int64)
        s[clamp_set] = -1
        acc = np.zeros(N); nacc = 0
        order = np.arange(N)
        cset = set(clamp_set.tolist())
        for sweep in range(10):
            rng.shuffle(order)
            for i in order:
                if i in cset: continue
                h = beta * int(sum(int(s[j]) for j in parents[i])) + \
                    beta * int(sum(int(s[k]) for k in children[i]))
                p_up = 1.0/(1.0+math.exp(-2.0*h)) if abs(h) < 30 else (1.0 if h > 0 else 0.0)
                s[i] = 1 if rng.random() < p_up else -1
            if sweep >= 3:
                acc += (s + 1) / 2; nacc += 1
        return acc / nacc

    out = {"project": prefix, "N": N,
           "n_direct": int((cls == 2).sum()), "n_downstream": int((cls == 1).sum())}
    for eps in (0.01, 0.2):
        base = np.mean([run(eps, np.array([], dtype=int), 100 + r) for r in range(5)], axis=0)
        clmp = np.mean([run(eps, clamp, 100 + r) for r in range(5)], axis=0)
        rec = {}
        for label, mask in (("clean", cls == 0), ("downstream", cls == 1), ("direct", cls == 2)):
            if mask.sum() == 0: continue
            rec[label] = {"baseline": round(float(base[mask].mean()), 3),
                          "clamped": round(float(clmp[mask].mean()), 3),
                          "delta": round(float((clmp - base)[mask].mean()), 3)}
        out[f"eps_{eps}"] = rec
    print(json.dumps(out, indent=1))
    json.dump(out, open(f"results/{prefix}_sorry_ising.json", "w"), indent=1)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
