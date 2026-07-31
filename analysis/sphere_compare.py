r"""Compare human-led vs AI-completed (Math Inc/Gauss) sphere packing repos."""
import json
import numpy as np
import networkx as nx
from networkx.algorithms import community as nxcom
import sys
sys.path.insert(0, 'analysis')
from analyze import powerlaw_alpha, adjacency_lists, firewall_delta

H = json.load(open("graphs/sphere_lean.json"))       # human-led (thefundamentaltheor3m)
M = json.load(open("graphs/mathinc_sphere_lean.json"))  # Math Inc (AI-completed + dim24)

hnames = {d["full"] for d in H["decls"]}
mnames = {d["full"] for d in M["decls"]}
inter = hnames & mnames
print(f"human decls {len(hnames)}, mathinc decls {len(mnames)}, shared names {len(inter)}")
print(f"mathinc new decls: {len(mnames - hnames)}")

for tag, data in [("human_led", H), ("mathinc", M)]:
    G = nx.DiGraph(); G.add_nodes_from(range(len(data["decls"])))
    G.add_edges_from(data["edges"])
    wcc = max(nx.weakly_connected_components(G), key=len)
    L = G.subgraph(wcc)
    outdeg = [dd for _, dd in L.out_degree()]
    alpha, sigma, fit = powerlaw_alpha(outdeg)
    U = L.to_undirected()
    coms = list(nxcom.greedy_modularity_communities(U))
    Q = nxcom.modularity(U, coms)
    nodes = list(L.nodes())
    parents, children = adjacency_lists(L, nodes)
    idx = {n: i for i, n in enumerate(nodes)}
    dl1, nm = firewall_delta(parents, children, [[idx[n] for n in c] for c in coms], idx)
    print(json.dumps({"repo": tag, "N": G.number_of_nodes(), "E": G.number_of_edges(),
                      "N_lwcc": L.number_of_nodes(),
                      "n_wcc": nx.number_weakly_connected_components(G),
                      "mean_out": round(float(np.mean(outdeg)), 2),
                      "max_out": int(max(outdeg)),
                      "alpha": alpha, "alpha_sigma": sigma, "fit": fit,
                      "modularity_Q": round(float(Q), 3),
                      "DeltaL1": dl1, "n_modules_used": nm}))

# Which files are AI-era? Compare per-directory decl counts between repos
from collections import Counter
hd = Counter(d["file"].split('/')[0] for d in H["decls"])
md = Counter(d["file"].split('/')[0] for d in M["decls"])
print("\nper-topdir decl counts (human -> mathinc):")
for k in sorted(set(hd) | set(md), key=lambda k: -(md.get(k,0))):
    print(f"  {k:35s} {hd.get(k,0):5d} -> {md.get(k,0):5d}")
