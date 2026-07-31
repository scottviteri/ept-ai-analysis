r"""Extract dependency graph from a leanblueprint LaTeX source tree.

Nodes: \label{...} of statement environments (definition/lemma/theorem/...).
Edges: u -> v when v (statement or its proof) has \uses{...u...}.
Also records \lean{...} tags mapping blueprint nodes to Lean declaration names,
and \leanok status.
"""
import re, sys, json, os, glob

STMT_ENVS = {"definition", "lemma", "theorem", "proposition", "corollary",
             "sublemma", "conjecture", "example", "claim"}

def strip_comments(tex):
    # remove LaTeX comments (unescaped %)
    return re.sub(r'(?<!\\)%.*', '', tex)

def parse_tex(tex, nodes, edges):
    # scan environments in order
    env_re = re.compile(r'\\begin\{(' + '|'.join(STMT_ENVS | {"proof"}) + r')\}(.*?)\\end\{\1\}', re.S)
    cur_label = None
    for m in env_re.finditer(tex):
        env, body = m.group(1), m.group(2)
        uses = []
        for um in re.finditer(r'\\uses\{([^}]*)\}', body):
            uses += [u.strip() for u in um.group(1).split(',') if u.strip()]
        if env == "proof":
            if cur_label:
                nodes[cur_label]["proved_in_blueprint"] = True
                if re.search(r'\\leanok', body):
                    nodes[cur_label]["proof_leanok"] = True
                for u in uses:
                    edges.add((u, cur_label))
        else:
            lm = re.search(r'\\label\{([^}]*)\}', body)
            if not lm:
                cur_label = None
                continue
            label = lm.group(1).strip()
            leanm = re.findall(r'\\lean\{([^}]*)\}', body)
            leans = []
            for lgroup in leanm:
                leans += [x.strip() for x in lgroup.split(',') if x.strip()]
            nodes.setdefault(label, {"env": env, "lean": leans,
                                     "stmt_leanok": bool(re.search(r'\\leanok', body)),
                                     "proved_in_blueprint": False, "proof_leanok": False})
            for u in uses:
                edges.add((u, label))
            cur_label = label

def main(bp_dir, out_json):
    if not os.path.isdir(bp_dir):
        sys.exit(f"error: {bp_dir} does not exist — run fetch_repos.sh first")
    nodes, edges = {}, set()
    texs = sorted(glob.glob(os.path.join(bp_dir, '**', '*.tex'), recursive=True))
    if not texs:
        sys.exit(f"error: no .tex files under {bp_dir}")
    for t in texs:
        try:
            tex = strip_comments(open(t, encoding='utf-8', errors='replace').read())
        except Exception as e:
            print("skip", t, e); continue
        parse_tex(tex, nodes, edges)
    # keep only edges whose source is a known node (drop dangling refs but count them)
    dangling = sorted({u for (u, v) in edges if u not in nodes})
    kept = [(u, v) for (u, v) in edges if u in nodes and v in nodes]
    out = {"nodes": nodes, "edges": kept, "dangling_sources": dangling,
           "n_tex_files": len(texs)}
    json.dump(out, open(out_json, 'w'))
    print(f"{bp_dir}: {len(nodes)} nodes, {len(kept)} edges "
          f"({len(dangling)} dangling source labels dropped)")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
