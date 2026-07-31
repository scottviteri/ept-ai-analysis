r"""Split Equational Theories declaration graph into human-authored vs
machine-generated (Generated/ subtree) and compare network structure."""
import json
import numpy as np
import networkx as nx
from networkx.algorithms import community as nxcom
import sys
sys.path.insert(0, 'analysis')
from analyze import powerlaw_alpha, adjacency_lists, firewall_delta

d = json.load(open("graphs/et_lean.json"))
decls = d["decls"]
gen = [i for i, x in enumerate(decls) if x["file"].startswith("Generated/")]
hum = [i for i, x in enumerate(decls) if not x["file"].startswith("Generated/")]
print(f"human decls: {len(hum)}, generated decls: {len(gen)}")

G = nx.DiGraph(); G.add_nodes_from(range(len(decls))); G.add_edges_from(d["edges"])

# cross-edges
genset, humset = set(gen), set(hum)
hh = sum(1 for u, v in G.edges() if u in humset and v in humset)
gg = sum(1 for u, v in G.edges() if u in genset and v in genset)
hg = sum(1 for u, v in G.edges() if u in humset and v in genset)
gh = sum(1 for u, v in G.edges() if u in genset and v in humset)
print(f"edges human->human {hh}, gen->gen {gg}, human->gen {hg}, gen->human {gh}")

for name, idxs in [("ET_human", hum), ("ET_generated", gen)]:
    H = G.subgraph(idxs).copy()
    wcc = max(nx.weakly_connected_components(H), key=len)
    L = H.subgraph(wcc)
    outdeg = [dd for _, dd in L.out_degree()]
    indeg = [dd for _, dd in L.in_degree()]
    alpha, sigma, fit = powerlaw_alpha(outdeg)
    U = L.to_undirected()
    coms = list(nxcom.greedy_modularity_communities(U))
    Q = nxcom.modularity(U, coms)
    nodes = list(L.nodes())
    parents, children = adjacency_lists(L, nodes)
    idx = {n: i for i, n in enumerate(nodes)}
    com_idx = [[idx[n] for n in c] for c in coms]
    dl1, nm = firewall_delta(parents, children, com_idx, idx)
    print(json.dumps({
        "name": name, "N": H.number_of_nodes(), "E": H.number_of_edges(),
        "N_lwcc": L.number_of_nodes(), "frac_in_lwcc": round(L.number_of_nodes()/H.number_of_nodes(), 3),
        "n_wcc": nx.number_weakly_connected_components(H),
        "mean_out": float(np.mean(outdeg)), "max_out": int(max(outdeg)),
        "alpha": alpha, "alpha_sigma": sigma, "fit": fit,
        "modularity_Q": round(float(Q), 3), "n_modules": len(coms),
        "DeltaL1": dl1, "DeltaL1_nmods": nm}, indent=1))

# per generation-method subdirectories
from collections import Counter, defaultdict
method = defaultdict(list)
for i in gen:
    parts = decls[i]["file"].split('/')
    method[parts[1] if len(parts) > 2 else parts[1].replace('.lean','')].append(i)
print("\nper-method decl counts and internal edge density:")
for m, idxs in sorted(method.items(), key=lambda kv: -len(kv[1]))[:12]:
    S = G.subgraph(idxs)
    print(f"  {m:35s} N={len(idxs):6d} E_int={S.number_of_edges():6d} "
          f"mean_out={S.number_of_edges()/max(len(idxs),1):.2f}")
