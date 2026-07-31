"""Finished vs unfinished proofs: blueprint status + kernel sorry propagation.

For each project with a kernel graph:
 - blueprint: fraction of nodes with proof_leanok / stmt only / nothing yet,
   and whether blueprint edges cross the finished/unfinished frontier;
 - kernel: declarations depending directly on sorryAx, and the transitive
   closure of contamination (everything whose proof rests on a sorry);
 - which top-degree hubs are contaminated.

usage: python3 analysis/sorry_analysis.py <prefix> <kernel_deps.jsonl> [blueprint.json]
"""
import json, sys
from collections import defaultdict, deque, Counter

def kernel_taint(jsonl):
    rows = [json.loads(l) for l in open(jsonl)]
    direct = {r["full"] for r in rows if "sorryAx" in r.get("ext_deps", [])}
    # edge dep -> user; contamination flows dep -> user
    users = defaultdict(list)
    for r in rows:
        for d in r["deps"]:
            if d != r["full"]:
                users[d].append(r["full"])
    tainted = set(direct)
    q = deque(direct)
    while q:
        x = q.popleft()
        for u in users[x]:
            if u not in tainted:
                tainted.add(u); q.append(u)
    kinds = Counter(r["kind"] for r in rows if r["full"] in direct)
    outdeg = Counter()
    for r in rows:
        for d in r["deps"]:
            if d != r["full"]:
                outdeg[d] += 1
    top_tainted_hubs = [(n, c) for n, c in outdeg.most_common(200) if n in tainted][:10]
    return {"n_decls": len(rows), "direct_sorry": len(direct),
            "direct_kinds": dict(kinds),
            "tainted": len(tainted),
            "frac_tainted": round(len(tainted)/len(rows), 3),
            "direct_names": sorted(direct)[:15],
            "top_tainted_hubs": top_tainted_hubs}

def blueprint_status(bp_json):
    g = json.load(open(bp_json))
    nodes = g["nodes"]
    done = {k for k, v in nodes.items() if v.get("proof_leanok")}
    stmt_only = {k for k, v in nodes.items() if v.get("stmt_leanok") and not v.get("proof_leanok")}
    unstarted = set(nodes) - done - stmt_only
    # frontier edges: finished node citing unfinished, and vice versa
    fin_on_unfin = unfin_on_fin = within_fin = within_unfin = 0
    for (src, dst) in g["edges"]:  # src used by dst
        s_done, d_done = src in done, dst in done
        if s_done and d_done: within_fin += 1
        elif not s_done and not d_done: within_unfin += 1
        elif d_done and not s_done: fin_on_unfin += 1
        else: unfin_on_fin += 1
    return {"n_nodes": len(nodes), "proof_done": len(done),
            "stmt_only": len(stmt_only), "unstarted": len(unstarted),
            "frac_done": round(len(done)/len(nodes), 3) if nodes else None,
            "edges_within_finished": within_fin,
            "edges_within_unfinished": within_unfin,
            "finished_citing_unfinished": fin_on_unfin,
            "unfinished_citing_finished": unfin_on_fin}

if __name__ == "__main__":
    prefix, jsonl = sys.argv[1], sys.argv[2]
    out = {"project": prefix, "kernel": kernel_taint(jsonl)}
    if len(sys.argv) > 3:
        out["blueprint"] = blueprint_status(sys.argv[3])
    print(json.dumps(out, indent=1))
    json.dump(out, open(f"results/{prefix}_sorry_analysis.json", "w"), indent=1)
