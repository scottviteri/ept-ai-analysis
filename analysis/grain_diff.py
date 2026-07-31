r"""Characterize the difference between kernel-grain and textual-grain graphs.

For a project with both graphs extracted, reports:
 - edge agreement (recall/precision) and how missed edges break down by the
   *kind* of the dependency (instance/def/theorem) and by whether the dep's
   name literally appears in the citing declaration's source (notation- or
   elaboration-mediated vs plain miss);
 - hub shifts: top out-degree nodes per grain and rank changes;
 - external load: most-referenced mathlib/core constants (library lock-in).

usage: python3 analysis/grain_diff.py <prefix> <kernel_deps.jsonl> <textual.json> <lean_src_root>
"""
import json, sys, re, os, glob
from collections import Counter, defaultdict

def load(prefix, kernel_jsonl, textual_json, src_root):
    rows = [json.loads(l) for l in open(kernel_jsonl)]
    kern_kind = {r["full"]: r["kind"] for r in rows}
    kern_edges = set()
    for r in rows:
        for d in r["deps"]:
            if d != r["full"]:
                kern_edges.add((d, r["full"]))
    text = json.load(open(textual_json))
    tnames = [d["full"] for d in text["decls"]]
    text_edges = {(tnames[u], tnames[v]) for u, v in text["edges"]}
    shared = set(kern_kind) & set(tnames)
    ke = {(a, b) for (a, b) in kern_edges if a in shared and b in shared}
    te = {(a, b) for (a, b) in text_edges if a in shared and b in shared}

    out = {"project": prefix, "shared_decls": len(shared),
           "kernel_edges": len(ke), "textual_edges": len(te),
           "both": len(ke & te),
           "recall": round(len(ke & te) / len(ke), 3) if ke else None,
           "precision": round(len(ke & te) / len(te), 3) if te else None}

    # --- missed kernel edges: why? ---
    missed = ke - te
    by_kind = Counter(kern_kind.get(a, "?") for (a, b) in missed)
    out["missed_by_dep_kind"] = dict(by_kind.most_common())
    # does the dep's bare name appear anywhere in the citing decl's file text?
    # (if not, the use was injected by elaboration: instances, notation, tactics)
    file_of = {d["full"]: d["file"] for d in text["decls"]}
    src_cache = {}
    def src_text(fname):
        if fname not in src_cache:
            path = os.path.join(src_root, fname)
            src_cache[fname] = open(path, encoding="utf-8", errors="replace").read() \
                if os.path.exists(path) else ""
        return src_cache[fname]
    invisible = 0
    checked = 0
    for (a, b) in missed:
        f = file_of.get(b)
        if not f: continue
        checked += 1
        bare = a.split('.')[-1]
        if not re.search(r'(?<![A-Za-z0-9_])' + re.escape(bare) + r"(?![A-Za-z0-9_'])",
                         src_text(f)):
            invisible += 1
    out["missed_checked"] = checked
    out["missed_invisible_in_source"] = invisible
    out["frac_missed_invisible"] = round(invisible / checked, 3) if checked else None

    # --- spurious textual edges (not in kernel): likely comment/string/ambiguity hits
    out["textual_only_edges"] = len(te - ke)

    # --- hub shifts ---
    kout = Counter(a for (a, b) in ke)
    tout = Counter(a for (a, b) in te)
    out["top10_kernel_hubs"] = kout.most_common(10)
    out["top10_textual_hubs"] = tout.most_common(10)

    # --- external load (library lock-in) ---
    ext = Counter()
    for r in rows:
        for d in r.get("ext_deps", []):
            ext[d] += 1
    # drop structural noise (Eq, ofNat etc. still meaningful; keep all, report top)
    out["n_distinct_external"] = len(ext)
    out["total_external_refs"] = sum(ext.values())
    out["top20_external"] = ext.most_common(20)
    return out

if __name__ == "__main__":
    res = load(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    print(json.dumps(res, indent=1))
    json.dump(res, open(f"results/{sys.argv[1]}_grain_diff.json", "w"), indent=1)
