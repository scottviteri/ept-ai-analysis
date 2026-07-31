"""Extract a project-internal declaration reference graph from Lean 4 sources.

Nodes: named declarations (theorem/lemma/def/...) declared in the project.
Edges: A -> B when B's source text references A (A is a deductive precursor of B).

Textual (non-compiled) extraction: namespaces tracked for qualification;
references matched on fully-qualified or unambiguous suffix identifiers.
"""
import re, sys, json, os, glob
from collections import defaultdict

# Lean identifiers are Unicode: subscripts (z₁), Greek (φ₀, Φ₂), primes.
# [^\W\d] = any Unicode letter or underscore; \w covers letters, digits, and
# subscript digits/letters. ASCII-only classes here truncated z₁ -> z, merging
# distinct declarations into fake super-nodes, and missed Greek-initial names.
DECL_RE = re.compile(
    r'^(?P<indent>\s*)(?:@\[[^\]]*\]\s*)*'
    r'(?:private\s+|protected\s+|public\s+|noncomputable\s+|partial\s+|unsafe\s+|scoped\s+|nonrec\s+)*'
    r'(?P<kind>theorem|lemma|def|abbrev|instance|inductive|structure|class|opaque)\s+'
    r'(?P<name>[^\W\d«»][\w\'\.«»!?]*|«[^»]+»)',
    re.M)

NS_RE = re.compile(r'^\s*(namespace|end|section)\s*([\w\'\.]*)', re.M)
IDENT_RE = re.compile(r"[^\W\d][\w'\.!?]*")

def strip_comments(src):
    src = re.sub(r'/-([^-]|-(?!/))*-/', ' ', src, flags=re.S)  # block comments (incl docstrings)
    # string literals: error messages etc. contain phrases like `lemma with ...`
    # that otherwise match DECL_RE and become fake declarations
    src = re.sub(r'"(?:[^"\\]|\\.)*"', ' ', src, flags=re.S)
    src = re.sub(r'--.*', ' ', src)
    return src

def extract_decls(path, rel):
    src = strip_comments(open(path, encoding='utf-8', errors='replace').read())
    # find namespace context at each declaration position
    events = []  # (pos, 'ns'|'end', name)
    for m in NS_RE.finditer(src):
        kw, nm = m.group(1), m.group(2)
        events.append((m.start(), kw, nm))
    decls = []
    matches = list(DECL_RE.finditer(src))
    for i, m in enumerate(matches):
        pos = m.start()
        # reconstruct namespace stack at pos
        stack = []
        for (p, kw, nm) in events:
            if p > pos: break
            if kw == 'namespace' and nm:
                stack.extend(nm.split('.'))
            elif kw == 'section':
                stack.append(None)  # anonymous scope marker
            elif kw == 'end':
                k = len(nm.split('.')) if nm else 1
                for _ in range(k):
                    if stack: stack.pop()
        ns = [s for s in stack if s]
        # trailing '.' comes from universe annotations: `theorem foo.{u} ...`
        name = m.group('name').rstrip('.')
        full = '.'.join(ns + [name]) if ns else name
        end = matches[i+1].start() if i+1 < len(matches) else len(src)
        body = src[m.end():end]
        decls.append({"full": full, "bare": name, "kind": m.group('kind'),
                      "file": rel, "body": body})
    return decls

def main(root, out_json, subdir_filter=None):
    if not os.path.isdir(root):
        sys.exit(f"error: {root} does not exist — run fetch_repos.sh first")
    files = sorted(glob.glob(os.path.join(root, '**', '*.lean'), recursive=True))
    if not files:
        sys.exit(f"error: no .lean files under {root}")
    if subdir_filter:
        files = [f for f in files if subdir_filter in f]
    raw_decls = []
    for f in files:
        rel = os.path.relpath(f, root)
        raw_decls.extend(extract_decls(f, rel))
    # merge re-matched duplicates of the same fully-qualified name (e.g. the
    # same decl seen through different section scopes): one node, bodies joined
    all_decls, by_full = [], {}
    for d in raw_decls:
        if d["full"] in by_full:
            all_decls[by_full[d["full"]]]["body"] += "\n" + d["body"]
        else:
            by_full[d["full"]] = len(all_decls)
            all_decls.append(d)
    by_suffix = defaultdict(list)   # last component -> decl ids
    for i, d in enumerate(all_decls):
        parts = d["full"].split('.')
        for k in range(1, len(parts)+1):
            by_suffix['.'.join(parts[-k:])].append(i)
    edges = set()
    for i, d in enumerate(all_decls):
        seen = set()
        for m in IDENT_RE.finditer(d["body"]):
            tok = m.group(0).rstrip('.')
            if tok in seen: continue
            seen.add(tok)
            tgt = None
            if tok in by_full:
                cand = by_full[tok]
                # short global names (G, f, Ctx…) collide with local variable
                # names everywhere; only trust the match inside their own file
                if len(tok) > 3 or all_decls[cand]["file"] == d["file"]:
                    tgt = cand
            else:
                cands = by_suffix.get(tok, [])
                # unambiguous suffix match only, and token length > 3 to cut noise
                if len(set(all_decls[c]["full"] for c in cands)) == 1 and len(tok) > 3:
                    tgt = cands[0]
            if tgt is not None and tgt != i:
                edges.add((tgt, i))
    out = {"decls": [{k: d[k] for k in ("full", "bare", "kind", "file")} for d in all_decls],
           "edges": sorted(edges)}
    json.dump(out, open(out_json, 'w'))
    print(f"{root} [{subdir_filter or 'all'}]: {len(all_decls)} decls, {len(edges)} edges")

if __name__ == "__main__":
    sub = sys.argv[3] if len(sys.argv) > 3 else None
    main(sys.argv[1], sys.argv[2], sub)
