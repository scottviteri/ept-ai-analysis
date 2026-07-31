r"""Intra-proof claim networks from Lean tactic proofs.

For each theorem: nodes = named `have`/`obtain`/`set` bindings (claims made in
the course of the proof); edges = claim A referenced in the justification of
claim B (A -> B). Also collects style statistics (length, case-splits, tactic
histogram, nesting).
"""
import re, sys, json, glob, os
from collections import Counter

HAVE_RE = re.compile(r'\bhave\s+([A-Za-z_][A-Za-z0-9_\'!?]*)\s*[:=]')
ANON_RE = re.compile(r'\b(?:have|suffices)\s*:')
OBTAIN_RE = re.compile(r'\bobtain\s+⟨([^⟩]*)⟩')
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_'!?]*")
TACTIC_WORDS = ['simp', 'rw', 'nlinarith', 'linarith', 'omega', 'norm_num', 'ring',
                'field_simp', 'decide', 'aesop', 'exact', 'apply', 'refine', 'intro',
                'cases', 'rcases', 'obtain', 'induction', 'constructor', 'use',
                'interval_cases', 'positivity', 'gcongr', 'calc', 'have', 'suffices',
                'by_contra', 'contrapose', 'specialize', 'convert', 'push_neg', 'bound']

def strip_comments(src):
    src = re.sub(r'/-([^-]|-(?!/))*-/', ' ', src, flags=re.S)
    src = re.sub(r'--.*', ' ', src)
    return src

def theorem_blocks(src):
    decl = re.compile(r'^\s*(theorem|lemma)\s+([A-Za-z_][A-Za-z0-9_\'\.«»!?]*)', re.M)
    ms = list(decl.finditer(src))
    for i, m in enumerate(ms):
        end = ms[i+1].start() if i+1 < len(ms) else len(src)
        yield m.group(2), src[m.start():end]

def analyze_proof(name, text):
    stats = {"name": name, "n_lines": text.count('\n') + 1,
             "n_tokens": len(IDENT_RE.findall(text))}
    tl = Counter()
    for w in TACTIC_WORDS:
        c = len(re.findall(r'(?<![A-Za-z_.])' + w + r'(?![A-Za-z0-9_\'])', text))
        if c: tl[w] = c
    stats["tactics"] = dict(tl)
    stats["case_splits"] = tl.get('cases', 0) + tl.get('rcases', 0) + \
        tl.get('obtain', 0) + tl.get('interval_cases', 0) + tl.get('induction', 0)
    # claim graph
    stats["anon_claims"] = len(ANON_RE.findall(text))
    claims = []           # (name, pos)
    for m in HAVE_RE.finditer(text):
        if m.group(1) not in ('this',):
            claims.append((m.group(1), m.start()))
    for m in OBTAIN_RE.finditer(text):
        for nm in IDENT_RE.findall(m.group(1)):
            claims.append((nm, m.start()))
    # dedupe names keeping first occurrence order, allow shadowing (keep latest pos separately)
    edges = set()
    claim_names = {}
    for nm, pos in claims:
        claim_names.setdefault(nm, pos)
    ordered = sorted(claim_names.items(), key=lambda kv: kv[1])
    for i, (nm, pos) in enumerate(ordered):
        # segment justifying claim i: from its pos to next claim pos (crude)
        seg_end = ordered[i+1][1] if i+1 < len(ordered) else len(text)
        seg = text[pos:seg_end]
        for tok in set(IDENT_RE.findall(seg)):
            if tok != nm and tok in claim_names and claim_names[tok] < pos:
                edges.add((tok, nm))
    stats["n_claims"] = len(ordered)
    stats["n_claim_edges"] = len(edges)
    outdeg = Counter(u for u, v in edges)
    stats["claim_out_degrees"] = sorted(outdeg.values(), reverse=True)
    stats["max_claim_reuse"] = max(outdeg.values()) if outdeg else 0
    # nesting depth via indentation
    depths = [len(l) - len(l.lstrip()) for l in text.split('\n') if l.strip()]
    stats["max_indent"] = max(depths) if depths else 0
    stats["edges"] = sorted(edges)
    stats["claims"] = [nm for nm, _ in ordered]
    return stats

def main(paths, out_json):
    all_stats = []
    for p in paths:
        src = strip_comments(open(p, encoding='utf-8', errors='replace').read())
        for name, block in theorem_blocks(src):
            s = analyze_proof(name, block)
            s["file"] = p
            all_stats.append(s)
    json.dump(all_stats, open(out_json, 'w'), indent=1)
    for s in all_stats:
        print(f"{os.path.basename(s['file']):20s} {s['name'][:36]:36s} "
              f"lines={s['n_lines']:5d} named={s['n_claims']:3d} anon={s['anon_claims']:3d} "
              f"claim_edges={s['n_claim_edges']:4d} splits={s['case_splits']:3d} "
              f"max_reuse={s['max_claim_reuse']:3d} max_indent={s['max_indent']:3d}")

if __name__ == "__main__":
    main(sys.argv[1:-1], sys.argv[-1])
