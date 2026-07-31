r"""Compare kernel-grain (compiled) vs textual dependency graphs for a project.

Reads kernel_deps.jsonl (from extract_deps.lean), converts to the standard
{"decls": [...], "edges": [...]} shape, reruns the network battery, and
reports edge recall/precision of the textual graph on shared nodes.
Also reruns tracking fidelity on the kernel graph.
"""
import json, sys
import numpy as np
import networkx as nx
from networkx.algorithms import community as nxcom
sys.path.insert(0, 'analysis')
from analyze import powerlaw_alpha

def load_kernel(jsonl_path):
    decls, name2idx = [], {}
    rows = [json.loads(l) for l in open(jsonl_path) if l.strip()]
    for i, r in enumerate(rows):
        name2idx[r["full"]] = i
        decls.append({"full": r["full"], "bare": r["full"].split('.')[-1],
                      "kind": r["kind"], "file": r["file"]})
    edges = set()
    n_ext = 0
    for i, r in enumerate(rows):
        n_ext += r["n_external"]
        for d in r["deps"]:
            j = name2idx.get(d)
            if j is not None and j != i:
                edges.add((j, i))          # dep -> dependent
    return {"decls": decls, "edges": sorted(edges)}, n_ext

def battery(data, label):
    G = nx.DiGraph(); G.add_nodes_from(range(len(data["decls"])))
    G.add_edges_from(data["edges"])
    wcc = max(nx.weakly_connected_components(G), key=len)
    L = G.subgraph(wcc)
    outdeg = [d for _, d in L.out_degree()]
    alpha, sigma, fit = powerlaw_alpha(outdeg)
    U = L.to_undirected()
    coms = list(nxcom.greedy_modularity_communities(U))
    print(json.dumps({"graph": label, "N": G.number_of_nodes(),
                      "E": G.number_of_edges(), "N_lwcc": L.number_of_nodes(),
                      "mean_out": round(float(np.mean(outdeg)), 2),
                      "max_out": int(max(outdeg)),
                      "alpha": alpha and round(alpha, 3),
                      "alpha_sigma": sigma and round(sigma, 3),
                      "fit": fit,
                      "Q": round(float(nxcom.modularity(U, coms)), 3)}))
    return G

def main(jsonl_path, textual_path, out_path):
    kern, n_ext = load_kernel(jsonl_path)
    json.dump(kern, open(out_path, "w"))
    text = json.load(open(textual_path))
    print(f"external (mathlib/core) dep references from project decls: {n_ext}")
    battery(kern, "kernel-grain")
    battery(text, "textual-grain")
    # edge agreement on shared nodes (by full name)
    kn = {d["full"]: i for i, d in enumerate(kern["decls"])}
    tn = {d["full"]: i for i, d in enumerate(text["decls"])}
    shared = set(kn) & set(tn)
    print(f"decl-name overlap: {len(shared)} shared "
          f"(kernel {len(kn)}, textual {len(tn)})")
    def named_edges(data, idx2name, keep):
        out = set()
        names = [d["full"] for d in data["decls"]]
        for u, v in data["edges"]:
            a, b = names[u], names[v]
            if a in keep and b in keep:
                out.add((a, b))
        return out
    ke = named_edges(kern, None, shared)
    te = named_edges(text, None, shared)
    inter = ke & te
    print(f"edges on shared nodes: kernel {len(ke)}, textual {len(te)}, both {len(inter)}")
    print(f"textual recall of kernel edges: {len(inter)/len(ke):.3f}")
    print(f"textual precision: {len(inter)/len(te):.3f}")
    # transitive recall: textual-missed kernel edges realized as textual paths <=3
    Gt = nx.DiGraph(); Gt.add_edges_from(te)
    missed = ke - te
    ok = 0
    for (a, b) in missed:
        if Gt.has_node(a) and Gt.has_node(b):
            try:
                if nx.shortest_path_length(Gt, a, b) <= 3:
                    ok += 1
            except nx.NetworkXNoPath:
                pass
    if missed:
        print(f"missed kernel edges realized as textual paths <=3 hops: {ok}/{len(missed)}")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
