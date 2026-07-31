r"""EPT analysis of proof dependency networks (replicating Viteri & DeDeo 2022).

Metrics per graph: N, E, in/out degree stats, power-law alpha (discrete CSN MLE)
on out-degree, modularity Q, EPT certainty curve, f2 at eps=0.01, DeltaL1 firewall.
"""
import json, sys, math, random
import numpy as np
import networkx as nx
from networkx.algorithms import community as nxcom

def load_graph(path, kind):
    d = json.load(open(path))
    G = nx.DiGraph()
    if kind == "blueprint":
        for n in d["nodes"]:
            G.add_node(n)
        G.add_edges_from(d["edges"])
        meta = {n: d["nodes"][n] for n in d["nodes"]}
    else:
        for i, dec in enumerate(d["decls"]):
            G.add_node(i, **dec)
        G.add_edges_from(d["edges"])
        meta = None
    return G, meta

def powerlaw_alpha(degs, min_xmin=2, max_xmin=None):
    """Discrete power-law fit, Clauset-Shalizi-Newman: choose xmin by KS, alpha by MLE."""
    degs = np.array([d for d in degs if d >= 1])
    if len(degs) < 20:
        return None, None, len(degs)
    xmins = sorted(set(degs))
    if max_xmin:
        xmins = [x for x in xmins if x <= max_xmin]
    best = (None, None, np.inf, 0)
    for xmin in xmins:
        tail = degs[degs >= xmin]
        n = len(tail)
        if n < 10:
            break
        alpha = 1.0 + n / np.sum(np.log(tail / (xmin - 0.5)))
        # KS distance against fitted CDF (continuous approx)
        tail_sorted = np.sort(tail)
        emp_cdf = np.arange(1, n + 1) / n
        theo_cdf = 1 - (tail_sorted / (xmin - 0.5)) ** (1 - alpha)
        ks = np.max(np.abs(emp_cdf - theo_cdf))
        if ks < best[2]:
            best = (alpha, xmin, ks, n)
    alpha, xmin, ks, n = best
    sigma = (alpha - 1) / math.sqrt(n) if alpha else None
    return alpha, sigma, {"xmin": int(xmin), "ntail": int(n), "ks": float(ks)}

def adjacency_lists(G, nodes):
    idx = {n: i for i, n in enumerate(nodes)}
    parents = [[] for _ in nodes]   # j -> i edges: j is precursor (dep) of i
    children = [[] for _ in nodes]
    for u, v in G.edges():
        if u in idx and v in idx:
            parents[idx[v]].append(idx[u])
            children[idx[u]].append(idx[v])
    return parents, children

def glauber_run(parents, children, beta_dep, beta_imp, p_prior, sweeps=10, burn=3, rng=None):
    rng = rng or np.random.default_rng(0)
    N = len(parents)
    s = np.where(rng.random(N) < p_prior, 1, -1).astype(np.int64)
    belief_acc = np.zeros(N)
    nacc = 0
    order = np.arange(N)
    for sweep in range(sweeps):
        rng.shuffle(order)
        for i in order:
            h = beta_dep * int(sum(int(s[j]) for j in parents[i])) + \
                beta_imp * int(sum(int(s[k]) for k in children[i]))
            p_up = 1.0 / (1.0 + math.exp(-2.0 * h)) if abs(h) < 30 else (1.0 if h > 0 else 0.0)
            s[i] = 1 if rng.random() < p_up else -1
        if sweep >= burn:
            belief_acc += (s + 1) / 2
            nacc += 1
    return belief_acc / max(nacc, 1), s

def ept_curve(parents, children, sinks, eps_list, p_prior=0.75, reps=3):
    out = []
    for eps in eps_list:
        beta = 0.5 * math.log((1 - eps) / eps)
        m_all, m_sink = [], []
        for r in range(reps):
            b, _ = glauber_run(parents, children, beta, beta, p_prior,
                               rng=np.random.default_rng(100 + r))
            m_all.append(b.mean())
            m_sink.append(b[sinks].mean() if len(sinks) else float('nan'))
        out.append({"eps": eps, "belief_all": float(np.mean(m_all)),
                    "belief_final": float(np.mean(m_sink))})
    return out

def firewall_delta(parents, children, communities, nodes_idx, reps=50, rng=None):
    """DeltaL1: per-node log-likelihood advantage of module flips vs random flips, beta=1."""
    rng = rng or np.random.default_rng(7)
    # equilibrate at prior 0.5, beta=1
    _, s = glauber_run(parents, children, 1.0, 1.0, 0.5, sweeps=10, burn=9,
                       rng=np.random.default_rng(42))
    N = len(parents)
    # symmetric edge list
    edges = [(j, i) for i in range(N) for j in parents[i]]
    def energy_delta(flipset):
        fs = np.zeros(N, dtype=bool)
        fs[list(flipset)] = True
        dE = 0.0
        for (a, b) in edges:
            if fs[a] != fs[b]:
                dE += 2.0 * s[a] * s[b]   # E = -sum s_a s_b; flipping one end flips sign
        return dE
    vals = []
    for com in communities:
        com = [c for c in com if c < N]
        if len(com) < 10 or len(com) > N // 2:
            continue
        dE_mod = energy_delta(com)
        dE_rand = np.mean([energy_delta(rng.choice(N, size=len(com), replace=False))
                           for _ in range(reps)])
        vals.append((dE_rand - dE_mod) / len(com))
    return float(np.mean(vals)) if vals else None, len(vals)

def analyze(name, G, eps_list, do_ept=True, sink_top=5):
    # largest weakly connected component
    wcc = max(nx.weakly_connected_components(G), key=len)
    H = G.subgraph(wcc).copy()
    nodes = list(H.nodes())
    res = {"name": name, "N_total": G.number_of_nodes(), "E_total": G.number_of_edges(),
           "N_lwcc": H.number_of_nodes(), "E_lwcc": H.number_of_edges()}
    indeg = [d for _, d in H.in_degree()]
    outdeg = [d for _, d in H.out_degree()]
    res["mean_in"] = float(np.mean(indeg)); res["mean_out"] = float(np.mean(outdeg))
    res["max_out"] = int(max(outdeg)) if outdeg else 0
    alpha, sigma, fit = powerlaw_alpha(outdeg)
    res["alpha"] = alpha; res["alpha_sigma"] = sigma; res["alpha_fit"] = fit
    # depth (longest path in DAG; graphs may have cycles from noise -> use approximation)
    try:
        res["dag_depth"] = int(nx.dag_longest_path_length(H))
    except Exception:
        res["dag_depth"] = None
    # communities on undirected version
    U = H.to_undirected()
    if U.number_of_nodes() > 5000:
        coms = list(nxcom.louvain_communities(U, seed=1))
    else:
        coms = list(nxcom.greedy_modularity_communities(U))
    res["n_modules"] = len(coms)
    res["modularity_Q"] = float(nxcom.modularity(U, coms))
    parents, children = adjacency_lists(H, nodes)
    idx = {n: i for i, n in enumerate(nodes)}
    com_idx = [[idx[n] for n in c] for c in coms]
    dl1, nmods = firewall_delta(parents, children, com_idx, idx)
    res["DeltaL1"] = dl1; res["DeltaL1_nmods"] = nmods
    if do_ept:
        # sinks: nodes with no dependents, ranked by in-degree (main results)
        sinks = [idx[n] for n in nodes if H.out_degree(n) == 0]
        sinks = sorted(sinks, key=lambda i: -len(parents[i]))[:sink_top]
        res["ept"] = ept_curve(parents, children, sinks, eps_list)
        f2 = [p for p in res["ept"] if abs(p["eps"] - 0.01) < 1e-9]
        res["f2_eps01"] = f2[0]["belief_final"] if f2 else None
    return res

if __name__ == "__main__":
    graphs = [
        ("pfr_blueprint", "graphs/pfr_blueprint.json", "blueprint"),
        ("flt_blueprint", "graphs/flt_blueprint.json", "blueprint"),
        ("sphere_blueprint", "graphs/sphere_blueprint.json", "blueprint"),
        ("et_blueprint", "graphs/et_blueprint.json", "blueprint"),
        ("pfr_lean", "graphs/pfr_lean.json", "lean"),
        ("sphere_lean", "graphs/sphere_lean.json", "lean"),
        ("flt_lean", "graphs/flt_lean.json", "lean"),
        ("et_lean", "graphs/et_lean.json", "lean"),
    ]
    eps_list = [0.4, 0.3, 0.2, 0.15, 0.1, 0.07, 0.05, 0.03, 0.02, 0.01, 0.005, 0.002]
    results = []
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for (name, path, kind) in graphs:
        if only and only != name:
            continue
        G, meta = load_graph(path, kind)
        print(f"analyzing {name}: {G.number_of_nodes()} nodes ...", flush=True)
        r = analyze(name, G, eps_list, do_ept=True)
        results.append(r)
        print(json.dumps({k: v for k, v in r.items() if k != "ept"}, indent=1))
    out = f"results_{only or 'all'}.json"
    json.dump(results, open(out, "w"), indent=1)
    print("saved", out)
