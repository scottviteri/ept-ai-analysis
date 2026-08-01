r"""What graph structure produces the 2022 phenomenology?

Runs the asymmetric-Ising belief model on the real PFR kernel network and on a
ladder of null models that each destroy one structural ingredient while
controlling the others:

  real     — PFR kernel LWCC as extracted
  module   — degree-preserving edge swaps *within* Louvain modules
             (keeps degree sequence/alpha AND modularity; destroys fine wiring)
  config   — degree-preserving edge swaps globally
             (keeps degree sequence/alpha; destroys modularity + hierarchy)
  dag      — order-respecting stub rematch on a random topological order
             (keeps approximate degree sequence + acyclicity; destroys modularity)
  er       — Erdos-Renyi with same N, E (destroys everything incl. hubs)

For each: EPT curve (mean belief and final-theorem belief vs eps), transition
location/sharpness, modularity Q, and the DeltaL1 firewall statistic.

Then, on the real graph, a beta_dep vs beta_imp asymmetry sweep at fixed total
coupling: what forward (trust in premises) vs backward (support from believed
consequences) strength each contribute.

usage: python3 analysis/null_models.py [graph.json] [out.json]
"""
import json, sys, math, random
import numpy as np
import networkx as nx
import networkx.algorithms.community as nxcom

sys.path.insert(0, 'analysis')
from analyze import glauber_run, adjacency_lists, firewall_delta, powerlaw_alpha

EPS_LIST = [0.4, 0.35, 0.3, 0.25, 0.2, 0.15, 0.1, 0.07, 0.05, 0.03, 0.02, 0.01]
REPS = 3
FINAL = "PFR_conjecture'"  # overridden by argv[3]

def load_lwcc(path):
    d = json.load(open(path))
    names = [x["full"] for x in d["decls"]]
    G = nx.DiGraph(); G.add_nodes_from(range(len(names)))
    G.add_edges_from(map(tuple, d["edges"]))
    wcc = max(nx.weakly_connected_components(G), key=len)
    H = G.subgraph(wcc).copy()
    mapping = {n: i for i, n in enumerate(sorted(H.nodes()))}
    H = nx.relabel_nodes(H, mapping)
    label = {}
    for old, new in mapping.items():
        label[new] = names[old]
    final_idx = next((i for i, n in label.items() if n == FINAL), None)
    return H, label, final_idx

def edge_swap(G, edges, allowed_pair, tries_mult=20, rng=None):
    """Directed double-edge swap (a->b, c->d) => (a->d, c->b), preserving
    in/out degrees. allowed_pair(e1, e2) gates which pairs may swap."""
    rng = rng or random.Random(0)
    E = list(edges)
    eset = set(E)
    n_swapped = 0
    for _ in range(tries_mult * len(E)):
        i, j = rng.randrange(len(E)), rng.randrange(len(E))
        if i == j: continue
        (a, b), (c, d) = E[i], E[j]
        if not allowed_pair(E[i], E[j]): continue
        if a == d or c == b: continue
        if (a, d) in eset or (c, b) in eset: continue
        eset.discard((a, b)); eset.discard((c, d))
        eset.add((a, d)); eset.add((c, b))
        E[i], E[j] = (a, d), (c, b)
        n_swapped += 1
    H = nx.DiGraph(); H.add_nodes_from(G.nodes()); H.add_edges_from(eset)
    return H, n_swapped

def dag_control(G, rng=None):
    """Random topological order; rematch in-stubs of each node to out-stubs of
    earlier nodes (approximately preserves both degree sequences, exactly
    preserves acyclicity)."""
    rng = rng or random.Random(1)
    nodes = list(G.nodes()); rng.shuffle(nodes)
    rank = {n: i for i, n in enumerate(nodes)}
    out_stubs = {n: G.out_degree(n) for n in nodes}
    H = nx.DiGraph(); H.add_nodes_from(G.nodes())
    for v in nodes:
        k = G.in_degree(v)
        cands = [u for u in nodes[:rank[v]] if out_stubs[u] > 0 and u != v]
        if not cands: continue
        weights = [out_stubs[u] for u in cands]
        chosen = set()
        for _ in range(min(k, len(cands))):
            tot = sum(weights)
            r = rng.random() * tot
            acc = 0
            for ui, u in enumerate(cands):
                acc += weights[ui]
                if acc >= r: break
            if u in chosen: continue
            chosen.add(u)
            out_stubs[u] -= 1
            weights[ui] = 0
        for u in chosen:
            H.add_edge(u, v)
    return H

def battery(name, H, final_idx, eps_list=EPS_LIST, reps=REPS):
    nodes = list(H.nodes())
    parents, children = adjacency_lists(H, nodes)
    idx = {n: i for i, n in enumerate(nodes)}
    outdeg = [H.out_degree(n) for n in nodes]
    alpha, sigma, fit = powerlaw_alpha(outdeg)
    U = H.to_undirected()
    coms = list(nxcom.louvain_communities(U, seed=1))
    Q = float(nxcom.modularity(U, coms))
    com_idx = [[idx[n] for n in c] for c in coms]
    dl1, nmods = firewall_delta(parents, children, com_idx, idx)
    try:
        depth = int(nx.dag_longest_path_length(H))
    except Exception:
        depth = None
    fi = idx.get(final_idx) if final_idx is not None else None
    curve = []
    for eps in eps_list:
        beta = 0.5 * math.log((1 - eps) / eps)
        m_all, m_fin = [], []
        for r in range(reps):
            b, _ = glauber_run(parents, children, beta, beta, 0.75,
                               rng=np.random.default_rng(200 + r))
            m_all.append(b.mean())
            if fi is not None: m_fin.append(b[fi])
        curve.append({"eps": eps, "belief_all": float(np.mean(m_all)),
                      "belief_final": float(np.mean(m_fin)) if m_fin else None})
    # transition location: eps where belief_all crosses midpoint; sharpness: max slope
    ba = [c["belief_all"] for c in curve]
    lo, hi = min(ba), max(ba)
    mid = (lo + hi) / 2
    eps_c = None
    for k in range(len(curve) - 1):
        if (ba[k] - mid) * (ba[k + 1] - mid) <= 0:
            e0, e1, b0, b1 = curve[k]["eps"], curve[k+1]["eps"], ba[k], ba[k+1]
            eps_c = e0 + (mid - b0) * (e1 - e0) / (b1 - b0) if b1 != b0 else e0
            break
    slopes = [abs((ba[k+1] - ba[k]) / (curve[k+1]["eps"] - curve[k]["eps"]))
              for k in range(len(curve) - 1)]
    return {"name": name, "N": len(nodes), "E": H.number_of_edges(),
            "alpha": alpha, "alpha_sigma": sigma, "Q": round(Q, 3),
            "DeltaL1": None if dl1 is None else round(dl1, 2),
            "dag_depth": depth,
            "eps_c": None if eps_c is None else round(eps_c, 4),
            "max_slope": round(max(slopes), 2), "belief_range": [round(lo,3), round(hi,3)],
            "curve": curve}

def asymmetry_sweep(H, final_idx, eps_grid=(0.05, 0.15, 0.25)):
    """Fixed total coupling 2*beta(eps); split between beta_dep (forward: node
    couples to its premises) and beta_imp (backward: to its dependents)."""
    nodes = list(H.nodes())
    parents, children = adjacency_lists(H, nodes)
    idx = {n: i for i, n in enumerate(nodes)}
    fi = idx.get(final_idx) if final_idx is not None else None
    out = []
    for eps in eps_grid:
        beta = 0.5 * math.log((1 - eps) / eps)
        for w in (0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0):
            bd, bi = beta * w, beta * (2 - w)
            m_all, m_fin = [], []
            for r in range(REPS):
                b, _ = glauber_run(parents, children, bd, bi, 0.75,
                                   rng=np.random.default_rng(300 + r))
                m_all.append(b.mean())
                if fi is not None: m_fin.append(b[fi])
            out.append({"eps": eps, "w_dep": w,
                        "beta_dep": round(bd, 3), "beta_imp": round(bi, 3),
                        "belief_all": round(float(np.mean(m_all)), 3),
                        "belief_final": round(float(np.mean(m_fin)), 3) if m_fin else None})
    return out

if __name__ == "__main__":
    gpath = sys.argv[1] if len(sys.argv) > 1 else "graphs/pfr_kernel.json"
    opath = sys.argv[2] if len(sys.argv) > 2 else "results/null_models.json"
    if len(sys.argv) > 3:
        globals()["FINAL"] = sys.argv[3]
    H, label, final_idx = load_lwcc(gpath)
    print(f"real: N={H.number_of_nodes()} E={H.number_of_edges()} final={label.get(final_idx)}", flush=True)

    U = H.to_undirected()
    coms = list(nxcom.louvain_communities(U, seed=1))
    com_of = {}
    for ci, c in enumerate(coms):
        for n in c: com_of[n] = ci

    rng = random.Random(42)
    graphs = {"real": H}
    Hm, ns = edge_swap(H, H.edges(),
                       lambda e1, e2: com_of[e1[0]] == com_of[e2[0]] == com_of[e1[1]] == com_of[e2[1]],
                       rng=rng)
    print(f"module-preserving rewire: {ns} swaps", flush=True)
    graphs["module"] = Hm
    Hc, ns = edge_swap(H, H.edges(), lambda e1, e2: True, rng=rng)
    print(f"global rewire: {ns} swaps", flush=True)
    graphs["config"] = Hc
    graphs["dag"] = dag_control(H)
    er = nx.gnm_random_graph(H.number_of_nodes(), H.number_of_edges(), seed=7, directed=True)
    graphs["er"] = er

    results = {"controls": [], "asymmetry": None}
    for name, G in graphs.items():
        fi = final_idx if name != "er" else None
        r = battery(name, G, fi)
        print(json.dumps({k: v for k, v in r.items() if k != "curve"}), flush=True)
        results["controls"].append(r)

    print("asymmetry sweep on real graph...", flush=True)
    results["asymmetry"] = asymmetry_sweep(H, final_idx)
    for row in results["asymmetry"]:
        print(row, flush=True)
    json.dump(results, open(opath, "w"), indent=1)
    print("saved", opath)
