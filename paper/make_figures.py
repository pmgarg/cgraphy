"""Generate paper figures from benchmark results.

Fig 1: hit@10 by repository and method (ordinal ramp: more graph signal =
       darker), repos sorted by lexical-baseline strength.
Fig 2: graph-signal gain vs lexical baseline strength (one point per repo).

Colors are the dataviz reference palette's ordinal blue ramp (validated
light-mode, steps 250/350/450/550) with chart chrome from the same system.
Usage: uv run --with matplotlib python paper/make_figures.py
"""
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
RAMP = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab"]  # fts→rank→expand-nc→expand
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, BASE, SURFACE = "#e1e0d9", "#c3c2b7", "#fcfcfb"
METHODS = ["fts", "rank", "expand-nc", "expand"]
LABELS = {"fts": "FTS (lexical)", "rank": "+PageRank",
          "expand-nc": "+expansion", "expand": "+co-change (full)"}

matplotlib.rcParams.update({
    "font.family": "sans-serif", "font.size": 9,
    "text.color": INK, "axes.edgecolor": BASE, "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.axisbelow": True, "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
})

data = json.load(open(HERE / "results.json"))
rows = data["localization_benchmark"]
rows.sort(key=lambda r: -r["results"]["fts"]["hit@10"])
repos = [r["repo"] for r in rows]
langs = {"click": "py", "requests": "py", "flask": "py", "fmt": "c++",
         "gin": "go", "ripgrep": "rust", "express": "js", "junit4": "java",
         "libuv": "c"}

# ---- Fig 1: grouped bars ----
fig, ax = plt.subplots(figsize=(6.4, 2.9), dpi=200)
n, w = len(repos), 0.19
for mi, m in enumerate(METHODS):
    xs = [i + (mi - 1.5) * (w + 0.012) for i in range(n)]
    ys = [r["results"][m]["hit@10"] for r in rows]
    ax.bar(xs, ys, width=w, color=RAMP[mi], label=LABELS[m],
           edgecolor=SURFACE, linewidth=0.8, zorder=3)
ax.set_xticks(range(n))
ax.set_xticklabels([f"{r}\n({langs[r]})" for r in repos], fontsize=8)
ax.set_ylabel("hit@10")
ax.set_ylim(0, 1.0)
ax.grid(axis="x", visible=False)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(frameon=False, ncol=4, loc="upper right", fontsize=7.5,
          bbox_to_anchor=(1.0, 1.14), handlelength=1.2, columnspacing=0.9)
fig.tight_layout()
fig.savefig(HERE / "fig_hit10.pdf", bbox_inches="tight")
fig.savefig(HERE / "fig_hit10.png", bbox_inches="tight")

# ---- Fig 2: gain vs baseline ----
fig, ax = plt.subplots(figsize=(4.0, 2.9), dpi=200)
xs = [r["results"]["fts"]["hit@10"] for r in rows]
ys = [r["results"]["expand"]["hit@10"] - r["results"]["fts"]["hit@10"]
      for r in rows]
ax.axhline(0, color=BASE, linewidth=1, zorder=2)
ax.scatter(xs, ys, s=42, color=RAMP[3], zorder=3)
OFFSETS = {"junit4": (-6, 4, "right"), "flask": (4, -11, "left"),
           "ripgrep": (-6, 4, "right"), "requests": (4, -11, "left")}
for r, x, y in zip(repos, xs, ys):
    dx, dy, ha = OFFSETS.get(r, (5, 4, "left"))
    ax.annotate(f"{r} ({langs[r]})", (x, y), textcoords="offset points",
                xytext=(dx, dy), ha=ha, fontsize=7.5, color=INK2)
ax.set_xlabel("lexical baseline strength (FTS hit@10)")
ax.set_ylabel("graph-signal gain\n(full − FTS, hit@10)")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig(HERE / "fig_gain.pdf", bbox_inches="tight")
fig.savefig(HERE / "fig_gain.png", bbox_inches="tight")
print("wrote fig_hit10.{pdf,png} fig_gain.{pdf,png}")
