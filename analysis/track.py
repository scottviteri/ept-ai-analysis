r"""Tracking fidelity: do blueprint (informal) dependency edges get realized
as paths between the corresponding Lean declarations?

Operationalizes the 'tracking' condition of DeDeo & Duede's correspondence
problem. For each blueprint edge u->v with \lean{} tags on both ends, test:
 - direct: some lean decl of u is a direct parent of some lean decl of v
 - path_k: reachable within k hops in the Lean declaration graph
"""
import json, sys
import networkx as nx

def main(bp_path, lean_path, name):
    bp = json.load(open(bp_path))
    ln = json.load(open(lean_path))
    G = nx.DiGraph()
    full2id = {}
    for i, d in enumerate(ln["decls"]):
        G.add_node(i)
        full2id.setdefault(d["full"], i)
        # also index bare name and suffix
        full2id.setdefault(d["bare"], i)
    G.add_edges_from(ln["edges"])
    nodes = bp["nodes"]
    tagged = {lab: [full2id[t] for t in nodes[lab]["lean"] if t in full2id]
              for lab in nodes if nodes[lab]["lean"]}
    tagged = {k: v for k, v in tagged.items() if v}
    n_tagged = len(tagged)
    edges = [(u, v) for (u, v) in bp["edges"] if u in tagged and v in tagged]
    direct = 0; path3 = 0; anypath = 0
    reach_cache = {}
    for (u, v) in edges:
        us, vs = tagged[u], tagged[v]
        d = any(G.has_edge(a, b) for a in us for b in vs)
        p3 = d
        ap = d
        if not d:
            for a in us:
                if a not in reach_cache:
                    lengths = nx.single_source_shortest_path_length(G, a, cutoff=6)
                    reach_cache[a] = lengths
                for b in vs:
                    L = reach_cache[a].get(b)
                    if L is not None:
                        ap = True
                        if L <= 3: p3 = True
        direct += d; path3 += p3; anypath += ap
    n = len(edges)
    res = {"project": name,
           "bp_nodes": len(nodes), "bp_edges": len(bp["edges"]),
           "lean_decls": len(ln["decls"]),
           "resolution_ratio": round(len(ln["decls"]) / max(len(nodes), 1), 2),
           "bp_nodes_with_lean_tag": n_tagged,
           "tag_coverage": round(n_tagged / max(len(nodes), 1), 3),
           "testable_edges": n,
           "direct_realized": round(direct / n, 3) if n else None,
           "path3_realized": round(path3 / n, 3) if n else None,
           "path6_realized": round(anypath / n, 3) if n else None}
    print(json.dumps(res, indent=1))
    return res

if __name__ == "__main__":
    out = []
    for (bp, lean, nm) in [("graphs/pfr_blueprint.json", "graphs/pfr_lean.json", "PFR"),
                           ("graphs/sphere_blueprint.json", "graphs/sphere_lean.json", "SpherePacking(human)"),
                           ("graphs/flt_blueprint.json", "graphs/flt_lean.json", "FLT"),
                           ("graphs/et_blueprint.json", "graphs/et_lean.json", "EquationalTheories")]:
        try:
            out.append(main(bp, lean, nm))
        except Exception as e:
            print(nm, "failed:", e)
    json.dump(out, open("tracking_results.json", "w"), indent=1)
