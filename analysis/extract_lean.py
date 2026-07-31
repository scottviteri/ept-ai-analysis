"""Extract a project-internal declaration reference graph from Lean 4 sources.

Nodes: named declarations (theorem/lemma/def/...) declared in the project.
Edges: A -> B when B's source text references A (A is a deductive precursor of B).

Textual (non-compiled) extraction: namespaces tracked for qualification;
references matched on fully-qualified or unambiguous suffix identifiers.
"""
import re, sys, json, os, glob
from collections import defaultdict

DECL_RE = re.compile(
    r'^(?P<indent>\s*)(?:@\[[^\]]*\]\s*)*'
    r'(?:private\s+|protected\s+|noncomputable\s+|partial\s+|unsafe\s+|scoped\s+)*'
    r'(?P<kind>theorem|lemma|def|abbrev|instance|inductive|structure|class|opaque)\s+'
    r'(?P<name>[A-Za-z_«][A-Za-z0-9_\'\.«»!?]*)',
    re.M)

NS_RE = re.compile(r'^\s*(namespace|end|section)\s*([A-Za-z0-9_\'\.]*)', re.M)
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_'\.!?]*")

def strip_comments(src):
    src = re.sub(r'/-([^-]|-(?!/))*-/', ' ', src, flags=re.S)  # block comments (incl docstrings)
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
        name = m.group('name')
        full = '.'.join(ns + [name]) if ns else name
        end = matches[i+1].start() if i+1 < len(matches) else len(src)
        body = src[m.end():end]
        decls.append({"full": full, "bare": name, "kind": m.group('kind'),
                      "file": rel, "body": body})
    return decls

def main(root, out_json, subdir_filter=None):
    files = sorted(glob.glob(os.path.join(root, '**', '*.lean'), recursive=True))
    if subdir_filter:
        files = [f for f in files if subdir_filter in f]
    all_decls = []
    for f in files:
        rel = os.path.relpath(f, root)
        all_decls.extend(extract_decls(f, rel))
    # name tables
    by_full = {}
    by_suffix = defaultdict(list)   # last component -> decl ids
    for i, d in enumerate(all_decls):
        by_full.setdefault(d["full"], i)
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
                tgt = by_full[tok]
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
