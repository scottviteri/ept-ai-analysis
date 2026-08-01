r"""Adversarial robustness tests for the headline claims.

1. Distribution shape: for each corpus's out-degree tail, fit discrete power
   law AND discrete lognormal (both truncated at the same xmin) and report the
   normalized Vuong log-likelihood ratio: positive = power law favored. Plus
   bootstrap CI for alpha and xmin-sensitivity band.
2. Jackknife by top-level module: refit alpha dropping each module.
3. Theorem-only subgraph: alpha when only theorem->theorem citation edges
   count (tests that *result* reuse, not just definition vocabulary, is
   heavy-tailed).

usage: python3 analysis/robustness.py
"""
import json, sys, math
import numpy as np
import networkx as nx
from scipy.optimize import minimize_scalar, minimize
from scipy.special import zeta

sys.path.insert(0, 'analysis')
from analyze import powerlaw_alpha


def fit_disc_powerlaw(tail, xmin):
    """discrete PL logL at MLE (via CSN)."""
    t = np.array([d for d in tail if d >= xmin], dtype=float)
    def nll(a):
        if a <= 1.0001: return 1e18
        z = zeta(a, xmin)
        return -( -a * np.log(t).sum() - len(t) * math.log(z) )
    r = minimize_scalar(nll, bounds=(1.01, 6), method='bounded')
    return -r.fun, r.x, len(t)

def fit_disc_lognormal(tail, xmin):
    """discrete (truncated at xmin) lognormal logL at MLE."""
    t = np.array([d for d in tail if d >= xmin], dtype=float)
    lo = np.log(t)
    def nll(p):
        mu, sig = p
        if sig <= 0.01: return 1e18
        # discrete: P(k) ~ integral over [k-0.5, k+0.5]; approximate by density
        # normalized over k >= xmin
        ks = np.arange(xmin, int(t.max()) * 3 + 10)
        dens = np.exp(-(np.log(ks) - mu) ** 2 / (2 * sig ** 2)) / ks
        Z = dens.sum()
        if not np.isfinite(Z) or Z <= 1e-300: return 1e18
        val = -((-(lo - mu) ** 2 / (2 * sig ** 2)) - np.log(t)).sum() + len(t) * math.log(Z)
        return val
    best = None
    for mu0 in (0.0, 1.0, 2.0):
        r = minimize(nll, x0=[mu0, 1.0], method='Nelder-Mead')
        if best is None or r.fun < best.fun: best = r
    return -best.fun, best.x, len(t)

def vuong(tail, xmin):
    """normalized LR statistic PL vs LN on shared tail; >0 favors PL.
    |R| < ~1.96 means the data cannot distinguish them."""
    t = np.array([d for d in tail if d >= xmin], dtype=float)
    n = len(t)
    if n < 10: return None, n
    llp, a, _ = fit_disc_powerlaw(tail, xmin)
    lll, (mu, sig), _ = fit_disc_lognormal(tail, xmin)
    # pointwise logL
    zp = zeta(a, xmin)
    lp = -a * np.log(t) - math.log(zp)
    ks = np.arange(xmin, int(t.max()) * 3 + 10)
    dens = np.exp(-(np.log(ks) - mu) ** 2 / (2 * sig ** 2)) / ks
    Z = dens.sum()
    ll = (-(np.log(t) - mu) ** 2 / (2 * sig ** 2)) - np.log(t) - math.log(Z)
    d = lp - ll
    R = d.sum() / (math.sqrt(n) * d.std() + 1e-12)
    return round(float(R), 2), n

def bootstrap_alpha(degs, B=200, seed=0):
    rng = np.random.default_rng(seed)
    degs = np.array(degs)
    alphas = []
    for _ in range(B):
        s = rng.choice(degs, size=len(degs), replace=True)
        a, _, _ = powerlaw_alpha(list(s))
        if a: alphas.append(a)
    return round(float(np.percentile(alphas, 2.5)), 2), round(float(np.percentile(alphas, 97.5)), 2)

def xmin_band(degs):
    """alpha across a range of manually forced xmin values."""
    out = {}
    for xm in (3, 5, 8, 12, 20, 30):
        tail = [d for d in degs if d >= xm]
        if len(tail) < 20: continue
        ll, a, n = fit_disc_powerlaw(tail, xm)
        out[xm] = (round(float(a), 2), n)
    return out

def outdeg_of(path):
    g = json.load(open(path))
    G = nx.DiGraph(); G.add_nodes_from(range(len(g['decls'])))
    G.add_edges_from(map(tuple, g['edges']))
    wcc = max(nx.weakly_connected_components(G), key=len)
    L = G.subgraph(wcc)
    return g, L, [d for _, d in L.out_degree()]

if __name__ == '__main__':
    corpora = [
        ('pfr_kernel', 'graphs/pfr_kernel.json'),
        ('flt_kernel', 'graphs/flt_kernel.json'),
        ('sphere_kernel', 'graphs/sphere_kernel.json'),
        ('mathinc_kernel', 'graphs/mathinc_kernel.json'),
        ('et_kernel', 'graphs/et_kernel.json'),
        ('pfr_blueprint', None),  # blueprint shape differs; handled separately
    ]
    report = {}
    for name, path in corpora:
        if path is None: continue
        g, L, degs = outdeg_of(path)
        a, s, fit = powerlaw_alpha(degs)
        R, ntail = vuong(degs, fit['xmin'])
        lo, hi = bootstrap_alpha(degs, B=100 if len(degs) > 10000 else 200)
        band = xmin_band(degs)
        rec = {'alpha': round(a, 2), 'xmin': fit['xmin'], 'ntail': fit['ntail'],
               'vuong_R_pl_vs_ln': R, 'bootstrap95': [lo, hi], 'alpha_by_xmin': band}
        # theorem-only subgraph
        kinds = [d.get('kind') for d in g['decls']]
        thm = {i for i, k in enumerate(kinds) if k in ('theorem', 'lemma')}
        T = nx.DiGraph(); T.add_nodes_from(thm)
        T.add_edges_from((u, v) for u, v in map(tuple, g['edges']) if u in thm and v in thm)
        if T.number_of_edges() > 100:
            wcc = max(nx.weakly_connected_components(T), key=len)
            td = [d for _, d in T.subgraph(wcc).out_degree()]
            ta, ts, tf = powerlaw_alpha(td)
            rec['thm_only_alpha'] = ta and round(ta, 2)
            rec['thm_only_ntail'] = tf['ntail']
        # jackknife by top-level module (kernel 'file' is dotted module name)
        mods = [d['file'].split('.')[1] if '.' in d['file'] else d['file'] for d in g['decls']]
        uniq = sorted(set(mods))
        jack = []
        if 2 < len(uniq) <= 80:
            for m in uniq:
                keep = {i for i, mm in enumerate(mods) if mm != m}
                J = nx.DiGraph(); J.add_nodes_from(keep)
                J.add_edges_from((u, v) for u, v in map(tuple, g['edges']) if u in keep and v in keep)
                if J.number_of_edges() < 100: continue
                wj = max(nx.weakly_connected_components(J), key=len)
                jd = [d for _, d in J.subgraph(wj).out_degree()]
                ja, _, _ = powerlaw_alpha(jd)
                if ja: jack.append(round(ja, 2))
            if jack:
                rec['jackknife_alpha_range'] = [min(jack), max(jack)]
        report[name] = rec
        print(name, json.dumps(rec), flush=True)
    json.dump(report, open('results/robustness_alpha.json', 'w'), indent=1)
    print('saved results/robustness_alpha.json')
