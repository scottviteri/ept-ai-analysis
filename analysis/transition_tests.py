r"""Is it really a phase transition, is it really a power law, and is alpha
really the knob?

A. CSN goodness-of-fit: semiparametric bootstrap p-value for the discrete
   power-law fit on each kernel corpus (p > 0.1 = power law not rejected).
B. Transition existence on the real PFR kernel graph:
   - susceptibility chi(eps) = N * Var(magnetization) across samples: a true
     transition shows a peak at eps_c, a crossover a plateau;
   - hysteresis: equilibrate from all-believed vs all-doubted starts; the
     bistable band (where final states disagree) is the first-order signature.
C. Finite-size scaling: random induced subgraphs of the ET kernel LWCC at
   N = 1500 / 6000 / 24000; a real transition's max slope and chi peak grow
   with N, a crossover's stay flat.
D. The causal arm: synthetic directed configuration graphs at matched N and
   mean degree with out-degree ~ discrete power law, alpha in
   {1.8, 2.2, 2.6, 3.2, 4.0} plus Poisson; measure eps_c(alpha).
   Mean-field prediction: critical coupling ~ <k>/<k^2>, so heavier tails
   (smaller alpha) should push eps_c up.

usage: python3 analysis/transition_tests.py [part: A|B|C|D|all]
"""
import json, sys, math, random
import numpy as np
import networkx as nx
from scipy.special import zeta

sys.path.insert(0, 'analysis')
from analyze import powerlaw_alpha

# ---------------------------------------------------------------- dynamics
def make_adj(G):
    nodes = sorted(G.nodes()); idx = {n: i for i, n in enumerate(nodes)}
    N = len(nodes)
    parents = [[] for _ in range(N)]; children = [[] for _ in range(N)]
    for u, v in G.edges():
        parents[idx[v]].append(idx[u]); children[idx[u]].append(idx[v])
    return N, parents, children

def glauber_mags(N, parents, children, beta, seed, sweeps=14, burn=4, init=None):
    """returns per-sweep magnetizations after burn-in."""
    rng = np.random.default_rng(seed)
    if init == 'up':    s = np.ones(N, dtype=np.int64)
    elif init == 'down': s = -np.ones(N, dtype=np.int64)
    else: s = np.where(rng.random(N) < 0.75, 1, -1).astype(np.int64)
    order = np.arange(N)
    mags = []
    for sweep in range(sweeps):
        rng.shuffle(order)
        for i in order:
            h = beta * (sum(int(s[j]) for j in parents[i]) + sum(int(s[k]) for k in children[i]))
            p = 1 / (1 + math.exp(-2 * h)) if abs(h) < 30 else float(h > 0)
            s[i] = 1 if rng.random() < p else -1
        if sweep >= burn:
            mags.append(float(s.mean()))
    return mags

def beta_of(eps): return 0.5 * math.log((1 - eps) / eps)

# ---------------------------------------------------------------- A: GOF
def gof_pvalue(degs, B=100, seed=0):
    """CSN semiparametric bootstrap for the discrete power law."""
    a, sig, fit = powerlaw_alpha(degs)
    if not a: return None
    xmin, ks_emp = fit['xmin'], fit['ks']
    degs = np.array(degs)
    body = degs[degs < xmin]
    ntail = int((degs >= xmin).sum())
    rng = np.random.default_rng(seed)
    # sampler for discrete PL(a, xmin) by inverse CDF on a grid
    ks = np.arange(xmin, max(int(degs.max()) * 4, xmin + 1000))
    pmf = ks ** (-a); pmf /= pmf.sum()
    cdf = np.cumsum(pmf)
    worse = 0
    for b in range(B):
        n_from_tail = int(rng.binomial(len(degs), ntail / len(degs)))
        synth_tail = ks[np.searchsorted(cdf, rng.random(n_from_tail))]
        synth_body = rng.choice(body, size=len(degs) - n_from_tail, replace=True) if len(body) else np.array([], dtype=int)
        synth = np.concatenate([synth_body, synth_tail])
        aa, ss, ff = powerlaw_alpha(list(synth))
        if ff and ff['ks'] >= ks_emp: worse += 1
    return round(worse / B, 3), a, xmin, ntail

def part_A():
    out = {}
    for name in ('pfr', 'flt', 'sphere', 'mathinc', 'et'):
        g = json.load(open(f'graphs/{name}_kernel.json'))
        G = nx.DiGraph(); G.add_nodes_from(range(len(g['decls'])))
        G.add_edges_from(map(tuple, g['edges']))
        L = G.subgraph(max(nx.weakly_connected_components(G), key=len))
        degs = [d for _, d in L.out_degree()]
        B = 50 if len(degs) > 20000 else 100
        p, a, xmin, ntail = gof_pvalue(degs, B=B)
        out[name] = {'gof_p': p, 'alpha': round(a, 2), 'xmin': xmin, 'ntail': ntail, 'B': B}
        print(f"A {name}: GOF p={p} (alpha={a:.2f}, xmin={xmin}, ntail={ntail})", flush=True)
    return out

# ---------------------------------------------------------------- B: chi + hysteresis
def part_B(gpath='graphs/pfr_kernel.json'):
    g = json.load(open(gpath))
    G = nx.DiGraph(); G.add_nodes_from(range(len(g['decls'])))
    G.add_edges_from(map(tuple, g['edges']))
    L = G.subgraph(max(nx.weakly_connected_components(G), key=len))
    N, parents, children = make_adj(L)
    eps_list = [0.46, 0.44, 0.42, 0.40, 0.38, 0.36, 0.34, 0.32, 0.30, 0.27, 0.24, 0.20, 0.15, 0.10]
    chi_rows, hyst_rows = [], []
    for eps in eps_list:
        beta = beta_of(eps)
        mags = []
        for r in range(4):
            mags += glauber_mags(N, parents, children, beta, 900 + r)
        chi = N * float(np.var(mags))
        m_up = np.mean([np.mean(glauber_mags(N, parents, children, beta, 950 + r, init='up')) for r in range(2)])
        m_dn = np.mean([np.mean(glauber_mags(N, parents, children, beta, 970 + r, init='down')) for r in range(2)])
        chi_rows.append({'eps': eps, 'chi': round(chi, 1), 'm': round(float(np.mean(mags)), 3)})
        hyst_rows.append({'eps': eps, 'm_up': round(float(m_up), 3), 'm_down': round(float(m_dn), 3),
                          'gap': round(float(m_up - m_dn), 3)})
        print(f"B eps={eps}: chi={chi:.1f} m={np.mean(mags):.3f} | up={m_up:.3f} down={m_dn:.3f} gap={m_up-m_dn:.3f}", flush=True)
    return {'susceptibility': chi_rows, 'hysteresis': hyst_rows}

# ---------------------------------------------------------------- C: finite size
def part_C(gpath='graphs/et_kernel.json', sizes=(1500, 6000, 24000)):
    g = json.load(open(gpath))
    G = nx.DiGraph(); G.add_nodes_from(range(len(g['decls'])))
    G.add_edges_from(map(tuple, g['edges']))
    L = G.subgraph(max(nx.weakly_connected_components(G), key=len))
    all_nodes = list(L.nodes())
    eps_list = [0.46, 0.42, 0.38, 0.34, 0.30, 0.26, 0.22]
    out = []
    rng = random.Random(5)
    for size in sizes:
        sub = L.subgraph(rng.sample(all_nodes, size))
        sub = sub.subgraph(max(nx.weakly_connected_components(sub), key=len))
        N, parents, children = make_adj(sub)
        ms, chis = [], []
        for eps in eps_list:
            beta = beta_of(eps)
            mags = []
            for r in range(2):
                mags += glauber_mags(N, parents, children, beta, 1100 + r)
            ms.append(float(np.mean(mags)))
            chis.append(N * float(np.var(mags)))
        slopes = [abs((ms[k+1] - ms[k]) / (eps_list[k+1] - eps_list[k])) for k in range(len(ms) - 1)]
        rec = {'target_size': size, 'N_lwcc': N, 'max_slope': round(max(slopes), 2),
               'chi_peak': round(max(chis), 1),
               'm_curve': [round(m, 3) for m in ms]}
        out.append(rec)
        print(f"C N={N}: max_slope={rec['max_slope']} chi_peak={rec['chi_peak']}", flush=True)
    return {'eps_list': eps_list, 'sizes': out}

# ---------------------------------------------------------------- D: alpha knob
def synth_graph(alpha, N=1106, mean_out=4.83, seed=0, poisson=False):
    rng = np.random.default_rng(seed)
    if poisson:
        outd = rng.poisson(mean_out, N)
    else:
        # discrete PL(alpha) on {1..N}, then mix with zeros to hit mean_out
        ks = np.arange(1, N)
        pmf = ks.astype(float) ** (-alpha); pmf /= pmf.sum()
        mean_pl = float((ks * pmf).sum())
        f = min(1.0, mean_out / mean_pl)  # fraction of nodes with PL degree
        outd = np.where(rng.random(N) < f, ks[np.searchsorted(np.cumsum(pmf), rng.random(N))], 0)
    # in-degrees: same total, Poisson-ish via multinomial
    E = int(outd.sum())
    ind = rng.multinomial(E, np.ones(N) / N)
    # stub matching
    src = np.repeat(np.arange(N), outd); rng.shuffle(src)
    dst = np.repeat(np.arange(N), ind); rng.shuffle(dst)
    G = nx.DiGraph(); G.add_nodes_from(range(N))
    G.add_edges_from((int(a), int(b)) for a, b in zip(src, dst) if a != b)
    return G

def part_D():
    eps_list = [0.47, 0.45, 0.43, 0.41, 0.39, 0.37, 0.35, 0.32, 0.29, 0.26, 0.22, 0.18]
    out = []
    for label, alpha in [('1.8', 1.8), ('2.2', 2.2), ('2.6', 2.6), ('3.2', 3.2), ('4.0', 4.0), ('poisson', None)]:
        ms, chis = [], []
        G = synth_graph(alpha or 0, poisson=(alpha is None), seed=11)
        L = G.subgraph(max(nx.weakly_connected_components(G), key=len))
        N, parents, children = make_adj(L)
        k = np.array([L.out_degree(n) + L.in_degree(n) for n in sorted(L.nodes())], dtype=float)
        k2_over_k = float((k ** 2).mean() / k.mean())
        for eps in eps_list:
            beta = beta_of(eps)
            mags = []
            for r in range(3):
                mags += glauber_mags(N, parents, children, beta, 1300 + r)
            ms.append(float(np.mean(mags)))
            chis.append(N * float(np.var(mags)))
        lo, hi = min(ms), max(ms); mid = (lo + hi) / 2
        eps_c = None
        for j in range(len(ms) - 1):
            if (ms[j] - mid) * (ms[j+1] - mid) <= 0:
                e0, e1, b0, b1 = eps_list[j], eps_list[j+1], ms[j], ms[j+1]
                eps_c = round(e0 + (mid - b0) * (e1 - e0) / (b1 - b0), 3) if b1 != b0 else e0
                break
        eps_chi = eps_list[int(np.argmax(chis))]
        rec = {'alpha': label, 'N_lwcc': N, 'k2_over_k': round(k2_over_k, 1),
               'eps_c': eps_c, 'eps_chi_peak': eps_chi,
               'm_range': [round(lo, 3), round(hi, 3)]}
        out.append(rec)
        print(f"D alpha={label}: N={N} <k2>/<k>={k2_over_k:.1f} eps_c={eps_c} chi-peak at {eps_chi}", flush=True)
    return out

if __name__ == '__main__':
    part = sys.argv[1] if len(sys.argv) > 1 else 'all'
    res = {}
    if part in ('A', 'all'): res['gof'] = part_A()
    if part in ('B', 'all'): res['transition_pfr'] = part_B()
    if part in ('D', 'all'): res['alpha_knob'] = part_D()
    if part in ('C', 'all'): res['finite_size_et'] = part_C()
    fn = f'results/transition_tests_{part}.json'
    json.dump(res, open(fn, 'w'), indent=1)
    print('saved', fn)
