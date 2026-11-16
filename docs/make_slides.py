"""Build docs/CompuOpti_defense.pptx from results/*/summary.json and figures.

    python docs/make_slides.py
"""
import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
NAVY = RGBColor(0x1F, 0x2A, 0x44)
ACCENT = RGBColor(0x9C, 0x1B, 0x4B)

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


def slide(title):
    s = prs.slides.add_slide(BLANK)
    tb = s.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12.3), Inches(0.9))
    p = tb.text_frame.paragraphs[0]
    p.text = title
    p.font.size, p.font.bold, p.font.color.rgb = Pt(30), True, NAVY
    bar = s.shapes.add_shape(1, Inches(0.5), Inches(1.15), Inches(1.5), Inches(0.06))
    bar.fill.solid(); bar.fill.fore_color.rgb = ACCENT; bar.line.fill.background()
    return s


def bullets(s, lines, x=0.6, y=1.5, w=12.0, h=5.6, size=18):
    tf = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)).text_frame
    tf.word_wrap = True
    for n, line in enumerate(lines):
        p = tf.paragraphs[0] if n == 0 else tf.add_paragraph()
        lvl = len(line) - len(line.lstrip(" ")) and 1
        p.text = line.strip()
        p.level = lvl
        p.font.size = Pt(size - 3 * lvl)
        p.space_after = Pt(6)
    return tf


def image(s, path, x, y, w=None, h=None):
    if Path(path).exists():
        s.shapes.add_picture(str(path), Inches(x), Inches(y),
                             Inches(w) if w else None, Inches(h) if h else None)


def table(s, rows, x, y, w, col_w=None, size=12):
    shp = s.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w),
                             Inches(0.35 * len(rows)))
    t = shp.table
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            cell = t.cell(r, c)
            cell.text = str(val)
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(size)
                p.font.bold = r == 0
    if col_w:
        for c, cw in enumerate(col_w):
            t.columns[c].width = Inches(cw)


def load(name):
    f = RES / name / "summary.json"
    return json.loads(f.read_text()) if f.exists() else None


# 1 Title ------------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
tb = s.shapes.add_textbox(Inches(0.8), Inches(2.3), Inches(11.5), Inches(3)).text_frame
tb.text = "Staffing collaborators on projects"
tb.paragraphs[0].font.size, tb.paragraphs[0].font.bold = Pt(44), True
tb.paragraphs[0].font.color.rgb = NAVY
for txt, sz in (("Multi-objective scheduling for CompuOpti", 26),
                ("Decision Modelling – MSc AI, CentraleSupélec 2026-27 – Prof. V. Mousseau", 18)):
    p = tb.add_paragraph(); p.text = txt; p.font.size = Pt(sz)

# 2 Problem ----------------------------------------------------------------
s = slide("The problem: CompuOpti's staffing decision")
bullets(s, [
    "Assign every working day of every collaborator to (project, qualification) or to nothing",
    "Hard constraints",
    "  qualification: staff only work on skills they hold",
    "  uniqueness: at most one task per person per day",
    "  leave: nobody works on a vacation day",
    "  coverage: a project counts only if every n_jk person-days are delivered",
    "  single execution: each project done at most once",
    "Economics: gain g_j when completed, penalty c_j per day after due date d_j",
    "Goal: not one schedule but the set of non-dominated trade-offs for the CEO",
])

# 3 Model ------------------------------------------------------------------
s = slide("Mathematical model (MILP)")
bullets(s, [
    "Sets: H={1..h}, Q, S (Q_i^S, V_i^S), J (Q_j^J, n_jk, g_j, d_j, c_j)",
    "Variables",
    "  X_ijkt ∈ {0,1} – created only if k ∈ Q_i^S ∩ Q_j^J and t ∉ V_i^S (sparse)",
    "  Y_j ∈ {0,1} completed;  E_j, B_j end / start day;  L_j ≥ 0 delay",
    "  P_ij ∈ {0,1} person i works on j;  D_j duration;  F2, F3 max-type objectives",
    "Constraints",
    "  Σ_jk X_ijkt ≤ 1  ∀i,t         Σ_it X_ijkt = n_jk·Y_j  ∀j,k (coverage + no overstaffing)",
    "  t·X_ijkt ≤ E_j ,  B_j ≤ t + h(1−X_ijkt) ,  E_j − d_j ≤ L_j",
    "  X_ijkt ≤ P_ij ,  Σ_j P_ij ≤ F2 ,  D_j ≥ E_j − B_j + 1 − (h+1)(1−Y_j) ,  D_j ≤ F3",
    "Objectives:  max f1 = Σ_j (g_j Y_j − c_j L_j)    min f2 = F2    min f3 = F3",
], size=17)

# 4 Multi-objective method ------------------------------------------------
s = slide("Computing all non-dominated solutions: ε-constraint")
bullets(s, [
    "f2 = max #projects per collaborator (focus), f3 = longest project (time-to-delivery)",
    "Both are small integers → exact ε-constraint on (f2, f3), maximise profit",
    "Lexicographic tie-break (min (h+1)·f2 + f3 at optimal profit) → no weakly dominated points",
    "Nested loop:  eps3 ← f3(q) − 1 after each optimum q;  eps2 ← max f2 found − 1",
    "Always feasible (empty schedule) → terminates; every non-dominated point is found",
    "Speed-ups that keep exactness",
    "  profit upper bound inherited from less-constrained sub-problems",
    "  warm starts from the heuristic archive and previous optima",
    "  aggregated day-activity variables Z_jt and duration cuts",
    "Solvers: OR-Tools CP-SAT (default) and Gurobi (identical results on toy)",
])

# 5 Heuristic & generator --------------------------------------------------
s = slide("Heuristic and instance generator")
bullets(s, [
    "Randomised greedy with Pareto archive (GRASP-like)",
    "  projects ordered by gain / workload (+ noise, + due-date order)",
    "  each project placed in the window [s, s+eps3−1] that finishes earliest, max parallel staffing",
    "  caps eps2 / eps3 swept over their range → spread of trade-offs",
    "  skip projects whose net gain after penalties ≤ 0",
    "Independent validator re-checks every constraint for every reported solution",
    "Instance generator: staff, jobs, horizon, #skills, load = demand / capacity, vacation blocks",
    "Unit tests: toy optimum = 65, exact front non-dominated, validator catches violations",
])

# 6 Results table ----------------------------------------------------------
rows = [["Instance", "|S|", "|J|", "h", "#X vars", "best profit", "exact pts", "exact time (s)",
         "proven", "heur pts", "heur time (s)", "C(exact,heur)"]]
for name in ["toy", "medium", "large"]:
    d = load(name)
    if not d:
        continue
    I, ex, he = d["instance"], d.get("exact", {}), d["heuristic"]
    rows.append([name, I["n_staff"], I["n_jobs"], I["horizon"], I["n_x_variables"],
                 d["best_profit"]["profit"], ex.get("n_points", "-"), ex.get("total_time_s", "-"),
                 "yes" if ex.get("exact") else "no (time limit)", he["n_points"],
                 he["total_time_s"], d.get("coverage_exact_over_heur", "-")])
gen = RES / "generated" / "benchmark.json"
if gen.exists():
    for d in json.loads(gen.read_text()):
        I, ex, he = d["instance"], d.get("exact", {}), d["heuristic"]
        rows.append([I["instance"].replace("gen_", ""), I["n_staff"], I["n_jobs"], I["horizon"],
                     I["n_x_variables"], d["best_profit"]["profit"], ex.get("n_points", "-"),
                     ex.get("total_time_s", "-"), "yes" if ex.get("exact") else "no",
                     he["n_points"], he["total_time_s"], d.get("coverage_exact_over_heur", "-")])
s = slide("Results on provided and generated instances")
table(s, rows, 0.4, 1.5, 12.5, size=11)
bullets(s, ["C(A,B) = share of B's points weakly dominated by A (1.0 → heuristic never beats exact)"],
        y=6.6, h=0.6, size=13)

# 7-9 per-instance fronts & schedules -------------------------------------
for name in ["toy", "medium", "large"]:
    d = load(name)
    if not d:
        continue
    s = slide(f"{name.capitalize()} instance – objective space")
    image(s, RES / name / "pareto.png", 0.3, 1.4, w=12.7)
    b = d["best_profit"]
    bullets(s, [f"Max profit {b['profit']} ({b['n_completed']} projects, {b['n_late']} late) · "
                f"{d.get('exact', d['heuristic'])['n_points']} non-dominated points · "
                f"interactive version: results/{name}/pareto.html"], y=5.7, h=1, size=15)
    s = slide(f"{name.capitalize()} instance – decision space (schedules)")
    image(s, RES / name / "gantt_max_profit.png", 0.3, 1.35, h=2.9)
    image(s, RES / name / "gantt_compromise.png", 0.3, 4.3, h=2.9)

# 10 Insights --------------------------------------------------------------
s = slide("Insights and recommendations for Margaux Dourtille")
bullets(s, [
    "Delivering everything on time is cheap: 93% (medium) / 96% (large) of max profit with 0 late projects",
    "Focus is expensive: f2 ≤ 2 keeps 79% / 64% of profit, f2 = 1 only 47% / 36%",
    "  scarce skills must be shared across projects → train or hire for bottleneck qualifications",
    "Very short projects (small f3) kill profit: big projects need several people over several days",
    "Recommended: a compromise point (medium 322 · f2=3 · f3=5) rather than the max-profit plan",
    "Exact front proven up to ~10 projects; beyond, time-limited ε-constraint seeded by the heuristic",
    "Future work: hire / train for bottleneck skills, robust plans for vacation changes,",
    "  more criteria (number of late projects, makespan) with the same ε-constraint machinery",
])

out = ROOT / "docs" / "CompuOpti_defense.pptx"
prs.save(out)
print("saved", out)
