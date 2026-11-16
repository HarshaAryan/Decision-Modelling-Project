"""Visualisation: objective space (Pareto front) and decision space (Gantt)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from data_loader import Instance  # noqa: E402
from solution import Solution, evaluate, objective_vector  # noqa: E402

LABELS = ("Profit f1 (max)", "Max projects / staff f2 (min)", "Max project duration f3 (min)")


def _xyz(inst, sols):
    v = [objective_vector(inst, s) for s in sols]
    return [a[0] for a in v], [a[1] for a in v], [a[2] for a in v]


def plot_pareto(inst: Instance, exact: list[Solution], heuristic: list[Solution] | None,
                path: str | Path, title: str = "") -> None:
    """3-D front + the three 2-D projections, exact vs heuristic."""
    fig = plt.figure(figsize=(15, 4.6))
    ax = fig.add_subplot(1, 4, 1, projection="3d")
    sets = [("exact (ε-constraint)", exact, "tab:blue", "o")]
    if heuristic:
        sets.append(("heuristic", heuristic, "tab:orange", "^"))
    for name, sols, c, mk in sets:
        if not sols:
            continue
        x, y, z = _xyz(inst, sols)
        ax.scatter(y, z, x, c=c, marker=mk, s=35, label=name, depthshade=False)
    ax.set_xlabel("f2"); ax.set_ylabel("f3"); ax.set_zlabel("profit")
    ax.set_title("Objective space (3-D)")
    ax.legend(fontsize=7, loc="upper left")
    pairs = [(1, 0), (2, 0), (1, 2)]
    for p, (a, b) in enumerate(pairs):
        ax2 = fig.add_subplot(1, 4, p + 2)
        for name, sols, c, mk in sets:
            if not sols:
                continue
            v = [objective_vector(inst, s) for s in sols]
            ax2.scatter([q[a] for q in v], [q[b] for q in v], c=c, marker=mk, s=35,
                        alpha=0.75, label=name)
            for q in v:
                if c == "tab:blue":
                    ax2.annotate(str(q[0] if b != 0 else ""), (q[a], q[b]), fontsize=5,
                                 xytext=(2, 2), textcoords="offset points")
        ax2.set_xlabel(LABELS[a]); ax2.set_ylabel(LABELS[b])
        ax2.grid(alpha=0.3)
    fig.suptitle(title or f"Non-dominated solutions – {inst.name}")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_pareto_interactive(inst: Instance, exact: list[Solution],
                            heuristic: list[Solution] | None, path: str | Path) -> None:
    """Plotly 3-D scatter, hovering a point lists the completed projects."""
    import plotly.graph_objects as go

    fig = go.Figure()
    for name, sols, sym in (("exact", exact, "circle"), ("heuristic", heuristic or [], "diamond")):
        if not sols:
            continue
        ev = [evaluate(inst, s) for s in sols]
        fig.add_trace(go.Scatter3d(
            x=[e["max_projects_per_staff"] for e in ev],
            y=[e["max_duration"] for e in ev],
            z=[e["profit"] for e in ev],
            mode="markers", name=name, marker=dict(size=5, symbol=sym),
            text=[f"profit={e['profit']}<br>f2={e['max_projects_per_staff']} f3={e['max_duration']}"
                  f"<br>late={e['n_late']}<br>{', '.join(e['completed'])}" for e in ev],
            hoverinfo="text"))
    fig.update_layout(title=f"Pareto front – {inst.name}",
                      scene=dict(xaxis_title="f2 max projects/staff",
                                 yaxis_title="f3 max duration", zaxis_title="f1 profit"))
    fig.write_html(str(path), include_plotlyjs="cdn")


def plot_gantt(inst: Instance, sol: Solution, path: str | Path, title: str = "") -> None:
    """Decision space: one row per staff member, one cell per day."""
    h = inst.horizon
    cmap = plt.get_cmap("tab20")
    colors = {j: cmap(j % 20) for j in range(len(inst.jobs))}
    fig, ax = plt.subplots(figsize=(max(8, 0.42 * h + 2), 0.55 * len(inst.staff) + 1.8))
    for i, s in enumerate(inst.staff):
        for t in s.vacations:
            ax.barh(i, 1, left=t - 0.5, color="lightgrey", hatch="//", edgecolor="grey", lw=0.3)
    used = set()
    for (i, j, k, t) in sol.assignments:
        used.add(j)
        ax.barh(i, 1, left=t - 0.5, color=colors[j], edgecolor="white", lw=0.6)
        ax.text(t, i, f"{inst.jobs[j].name.replace('Job', 'J')}\n{k}", ha="center",
                va="center", fontsize=5.5)
    for j in used:
        d = inst.jobs[j].due_date
        rows = sorted({a[0] for a in sol.assignments if a[1] == j})
        ax.plot([d + 0.5] * 2, [min(rows) - 0.45, max(rows) + 0.45], color=colors[j],
                lw=1.2, ls=":")
    ax.set_yticks(range(len(inst.staff)))
    ax.set_yticklabels([s.name for s in inst.staff])
    ax.set_xticks(range(1, h + 1))
    ax.set_xlim(0.5, h + 0.5)
    ax.set_xlabel("day")
    ax.invert_yaxis()
    e = evaluate(inst, sol)
    ax.set_title(title or (f"{inst.name}: profit={e['profit']}, f2={e['max_projects_per_staff']}, "
                           f"f3={e['max_duration']}, late={e['n_late']}"), fontsize=9)
    handles = [Patch(color=colors[j], label=f"{inst.jobs[j].name} (due {inst.jobs[j].due_date})")
               for j in sorted(used)]
    handles.append(Patch(facecolor="lightgrey", hatch="//", label="vacation"))
    ax.legend(handles=handles, fontsize=6, bbox_to_anchor=(1.01, 1), loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
