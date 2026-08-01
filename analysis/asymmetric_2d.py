r"""The asymmetric Ising model of the 2022 paper, taken seriously in 2D.

The paper's published EPT curves set beta_dep = beta_imp "for simplicity";
the asymmetric model is introduced for a specific mechanism: raising beta_imp
relative to beta_dep lets disbelief in a *consequence* overwhelm the deductive
evidence for its premises (refutation flowing backward). Three experiments on
the PFR kernel network:

A. EPT curves at fixed ratio r = beta_imp/beta_dep in {0, 1/4, 1/2, 1, 2, 4}:
   beta_dep = beta(eps) swept, beta_imp = r*beta_dep. Reports belief in all
   claims / final theorem / axioms (nodes with no in-graph premises), and the
   transition location per ratio. Tests whether the symmetric simplification
   used in the battery distorts the EPT picture.

B. Full 2D phase plane: mean belief on a beta_dep x beta_imp grid.

C. Refutation: clamp one important node to FALSE at eps=0.05 and measure how
   much disbelief propagates into its premises (direct + 2-hop ancestors) as a
   function of r. The paper's Lakatos mechanism, quantified.

usage: python3 analysis/asymmetric_2d.py [graph.json] [final_name] [out.json]
"""
import json, sys, math
import numpy as np
import networkx as nx

sys.path.insert(0, 'analysis')

def load(path, final_name):
    d = json.load(open(path))
    names = [x["full"] for x in d["decls"]]
    G = nx.DiGraph(); G.add_nodes_from(range(len(names)))
    G.add_edges_from(map(tuple, d["edges"]))
    wcc = max(nx.weakly_connected_components(G), key=len)
    H = G.subgraph(wcc)
    nodes = sorted(H.nodes()); idx = {n: i for i, n in enumerate(nodes)}
    N = len(nodes)
    parents = [[] for _ in range(N)]; children = [[] for _ in range(N)]
    for u, v in H.edges():
        parents[idx[v]].append(idx[u]); children[idx[u]].append(idx[v])
    fi = idx.get(names.index(final_name)) if final_name in names else None
    axioms = [i for i in range(N) if not parents[i]]
    return N, parents, children, fi, axioms, [names[n] for n in nodes], idx, H

def run(N, parents, children, bd, bi, seed, clamp_neg=()):
    rng = np.random.default_rng(seed)
    s = np.where(rng.random(N) < 0.75, 1, -1).astype(np.int64)
    cset = set(clamp_neg)
    for i in cset: s[i] = -1
    acc = np.zeros(N); n = 0
    order = np.arange(N)
    for sweep in range(10):
        rng.shuffle(order)
        for i in order:
            if i in cset: continue
            h = bd * sum(int(s[j]) for j in parents[i]) + bi * sum(int(s[k]) for k in children[i])
            p = 1 / (1 + math.exp(-2 * h)) if abs(h) < 30 else float(h > 0)
            s[i] = 1 if rng.random() < p else -1
        if sweep >= 3: acc += (s + 1) / 2; n += 1
    return acc / n

if __name__ == "__main__":
    gpath = sys.argv[1] if len(sys.argv) > 1 else "graphs/pfr_kernel.json"
    final = sys.argv[2] if len(sys.argv) > 2 else "PFR_conjecture'"
    opath = sys.argv[3] if len(sys.argv) > 3 else "results/asymmetric_2d.json"
    N, parents, children, fi, axioms, names, idx, H = load(gpath, final)
    print(f"N={N} final={final} n_axioms={len(axioms)}", flush=True)
    out = {}

    # --- A: EPT curves per ratio ---
    eps_list = [0.4, 0.35, 0.3, 0.25, 0.2, 0.15, 0.1, 0.05, 0.02, 0.01]
    curves = {}
    for r in (0.0, 0.25, 0.5, 1.0, 2.0, 4.0):
        rows = []
        for eps in eps_list:
            beta = 0.5 * math.log((1 - eps) / eps)
            bs = [run(N, parents, children, beta, r * beta, 500 + k) for k in range(3)]
            b = np.mean(bs, axis=0)
            rows.append({"eps": eps, "all": round(float(b.mean()), 3),
                         "final": round(float(b[fi]), 3) if fi is not None else None,
                         "axioms": round(float(b[axioms].mean()), 3)})
        ba = [x["all"] for x in rows]
        lo, hi = min(ba), max(ba); mid = (lo + hi) / 2
        eps_c = None
        for k in range(len(ba) - 1):
            if (ba[k] - mid) * (ba[k + 1] - mid) <= 0:
                e0, e1, b0, b1 = eps_list[k], eps_list[k+1], ba[k], ba[k+1]
                eps_c = round(e0 + (mid - b0) * (e1 - e0) / (b1 - b0), 3) if b1 != b0 else e0
                break
        curves[str(r)] = {"eps_c": eps_c, "belief_range": [lo, hi], "curve": rows}
        print(f"ratio beta_imp/beta_dep={r}: eps_c={eps_c} range=[{lo},{hi}]", flush=True)
    out["ept_by_ratio"] = curves

    # --- B: 2D phase plane ---
    grid = [0.0, 0.15, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0]
    plane = []
    for bd in grid:
        row = []
        for bi in grid:
            bs = [run(N, parents, children, bd, bi, 600 + k) for k in range(2)]
            row.append(round(float(np.mean([b.mean() for b in bs])), 3))
        plane.append(row)
        print(f"bd={bd}: {row}", flush=True)
    out["phase_plane"] = {"grid": grid, "belief_all": plane}

    # --- C: refutation (clamp an important consequence to false) ---
    # target: highest out-degree *theorem-like* node's most-cited child? use the
    # node with max out-degree among those that have parents (a mid-level hub),
    # plus the final theorem itself.
    outdeg = [(len(children[i]), i) for i in range(N) if parents[i]]
    hub = max(outdeg)[1]
    anc1 = set(parents[hub])
    anc2 = set(a for p in anc1 for a in parents[p]) - anc1
    ref = {}
    beta = 0.5 * math.log((1 - 0.05) / 0.05)
    for r in (0.25, 1.0, 4.0):
        bd = beta * 2 / (1 + r); bi = beta * 2 * r / (1 + r)   # fixed total
        base = np.mean([run(N, parents, children, bd, bi, 700 + k) for k in range(3)], axis=0)
        clmp = np.mean([run(N, parents, children, bd, bi, 700 + k, clamp_neg=(hub,)) for k in range(3)], axis=0)
        ref[str(r)] = {
            "premises_1hop": {"base": round(float(base[list(anc1)].mean()), 3),
                               "clamped": round(float(clmp[list(anc1)].mean()), 3)},
            "premises_2hop": {"base": round(float(base[list(anc2)].mean()), 3),
                               "clamped": round(float(clmp[list(anc2)].mean()), 3)} if anc2 else None,
            "network": {"base": round(float(base.mean()), 3),
                         "clamped": round(float(clmp.mean()), 3)}}
        print(f"refute hub (r={r}): premises {ref[str(r)]['premises_1hop']}", flush=True)
    out["refutation"] = {"target": names[hub], "n_premises": len(anc1), "by_ratio": ref}

    json.dump(out, open(opath, "w"), indent=1)
    print("saved", opath)
