r"""Generate theme-aware figures (light+dark PNG pairs) for the report."""
import json
import numpy as np
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

THEMES = {
    "light": {"text": "#0b0b0b", "sub": "#52514e", "grid": "#d8d7d2",
              "series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#9061c9"]},
    "dark":  {"text": "#ffffff", "sub": "#c3c2b7", "grid": "#3a3a38",
              "series": ["#3987e5", "#d95926", "#199e70", "#c98500", "#a37fd6"]},
}

def style_ax(ax, th):
    ax.set_facecolor("none")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(th["grid"])
    ax.tick_params(colors=th["sub"], labelsize=9)
    ax.xaxis.label.set_color(th["sub"]); ax.yaxis.label.set_color(th["sub"])
    ax.title.set_color(th["text"])
    ax.grid(True, color=th["grid"], lw=0.5, alpha=0.6)

def outdegs(path, subset=None):
    d = json.load(open(path))
    G = nx.DiGraph(); G.add_nodes_from(range(len(d["decls"])))
    G.add_edges_from(d["edges"])
    if subset is not None:
        idxs = [i for i, x in enumerate(d["decls"]) if subset(x)]
        G = G.subgraph(idxs)
    return [dd for _, dd in G.out_degree()]

def ccdf(degs):
    degs = np.array([d for d in degs if d >= 1])
    xs = np.sort(degs)
    ys = 1.0 - np.arange(len(xs)) / len(xs)
    return xs, ys

# ---------- F1: CCDF ----------
series_f1 = [
    ("ET human stratum (α≈2.52)", outdegs("graphs/et_lean.json", lambda x: not x["file"].startswith("Generated/"))),
    ("ET machine stratum (no power law)", outdegs("graphs/et_lean.json", lambda x: x["file"].startswith("Generated/"))),
    ("Sphere Packing, AI-completed (α≈2.51)", outdegs("graphs/mathinc_sphere_lean.json")),
    ("PFR Lean (α≈2.52)", outdegs("graphs/pfr_lean.json")),
]
for mode, th in THEMES.items():
    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=150)
    fig.patch.set_alpha(0)
    markers = ["o", "s", "^", "D"]
    for i, (lab, degs) in enumerate(series_f1):
        xs, ys = ccdf(degs)
        ax.loglog(xs, ys, markers[i], ms=3.5, ls="none", color=th["series"][i],
                  label=lab, alpha=0.85)
    style_ax(ax, th)
    ax.set_xlabel("out-degree d (number of later claims that use this claim)")
    ax.set_ylabel("P(D ≥ d)")
    ax.set_title("Claim re-use in AI-era formal proofs")
    leg = ax.legend(frameon=False, fontsize=8.5, loc="lower left")
    for t in leg.get_texts(): t.set_color(th["text"])
    fig.tight_layout()
    fig.savefig(f"figs/f1_ccdf_{mode}.png", transparent=True)
    plt.close(fig)

# ---------- F2: certainty curves ----------
R = {r["name"]: r for r in json.load(open("results_all.json"))}
picks = [("pfr_blueprint", "PFR blueprint (informal grain, N=217)"),
         ("pfr_lean", "PFR Lean (formal grain, N=916)"),
         ("et_blueprint", "Equational Theories blueprint (N=115)"),
         ("sphere_lean", "Sphere Packing Lean, human-led (N=1062)")]
for mode, th in THEMES.items():
    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=150)
    fig.patch.set_alpha(0)
    for i, (k, lab) in enumerate(picks):
        pts = R[k]["ept"]
        xs = [p["eps"] for p in pts]
        ys = [p["belief_all"] for p in pts]
        ax.semilogx(xs, ys, "-", color=th["series"][i], lw=2, label=lab,
                    marker="o", ms=4)
    ax.invert_xaxis()
    style_ax(ax, th)
    ax.set_xlabel("single-step inference error rate ε (decreasing →)")
    ax.set_ylabel("mean degree of belief across proof")
    ax.set_title("Epistemic phase transitions persist in AI-era proof networks")
    ax.set_ylim(0.5, 1.02)
    leg = ax.legend(frameon=False, fontsize=8.5, loc="lower right")
    for t in leg.get_texts(): t.set_color(th["text"])
    fig.tight_layout()
    fig.savefig(f"figs/f2_ept_{mode}.png", transparent=True)
    plt.close(fig)

# ---------- F3: alpha dot plot ----------
rows = [  # (label, alpha, err, group)
    ("Euclid Elements (Coq, 2022)", 2.14, 0.02, 0),
    ("48 machine proofs mean (2022)", 2.15, 0.13, 0),
    ("Euclid original text (2022)", 1.97, 0.07, 0),
    ("Wiles FLT text (2022)", 3.39, 0.72, 0),
    ("PFR Lean", 2.52, 0.28, 1),
    ("FLT Lean", 2.47, 0.22, 1),
    ("Sphere Lean (human-led)", 2.97, 0.40, 1),
    ("ET human stratum", 2.52, 0.17, 1),
    ("PFR blueprint", 3.43, 0.54, 2),
    ("FLT blueprint", 3.28, 0.72, 2),
    ("Sphere blueprint", 4.64, 1.15, 2),
    ("ET blueprint", 2.41, 0.31, 2),
    ("Sphere AI-completed (Gauss)", 2.51, 0.11, 3),
    ("Dim24 pure-AI (Gauss)", 2.55, 0.14, 3),
    ("ET whole graph", 2.14, 0.10, 3),
    ("PFR kernel", 2.46, 0.23, 4),
    ("FLT kernel", 2.99, 0.29, 4),
    ("Sphere kernel (human-led)", 2.49, 0.19, 4),
    ("Sphere kernel (Gauss)", 2.56, 0.12, 4),
    ("ET kernel (whole project)", 2.88, 0.07, 4),
]
gnames = ["2022 baselines", "Human-led Lean (2023-26)", "Blueprints (informal)",
          "AI/machine-generated", "Kernel ground truth"]
for mode, th in THEMES.items():
    fig, ax = plt.subplots(figsize=(7.2, 6.4), dpi=150)
    fig.patch.set_alpha(0)
    ys = np.arange(len(rows))[::-1]
    for (lab, a, e, g), y in zip(rows, ys):
        ax.errorbar(a, y, xerr=e, fmt="o", ms=6, color=th["series"][g],
                    ecolor=th["series"][g], elinewidth=1.5, capsize=3)
    ax.axvline(2.0, color=th["sub"], lw=1, ls="--", alpha=0.7)
    ax.text(2.02, len(rows) - 0.4, "α = 2", color=th["sub"], fontsize=9)
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows], fontsize=9)
    style_ax(ax, th)
    for tick, (lab, a, e, g) in zip(ax.get_yticklabels()[::-1], rows[::1]):
        pass
    for tl, (lab, a, e, g) in zip(list(ax.get_yticklabels()), list(rows)):
        tl.set_color(th["text"])
    ax.set_xlabel("power-law exponent α of claim re-use (out-degree)")
    ax.set_title("The α≈2 re-use signature: who has it, who lost it")
    # group legend
    handles = [plt.Line2D([], [], marker="o", ls="none", color=th["series"][i],
                          label=gnames[i]) for i in range(len(gnames))]
    leg = ax.legend(handles=handles, frameon=False, fontsize=8.5, loc="lower right")
    for t in leg.get_texts(): t.set_color(th["text"])
    fig.tight_layout()
    fig.savefig(f"figs/f3_alpha_{mode}.png", transparent=True)
    plt.close(fig)

print("figures written")
