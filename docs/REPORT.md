# CompuOpti – Staffing collaborators on projects: technical report

Decision Modelling (MSc AI, CentraleSupélec 2026-27, Prof. V. Mousseau)

This report documents the models, algorithms and results in this repository. Everything here can be reproduced with the commands in the [README](../README.md).

---

## 1. Problem

The company has a set of collaborators and a set of candidate client projects over a horizon of working days. Each collaborator has qualifications and leave days. Each project needs a given number of person-days per qualification. It earns a gain if it is completed and pays a daily penalty for each day it finishes after its due date. We must assign every collaborator-day to one (project, qualification) pair, or leave it idle. Not every project can be staffed.

## 2. Notation (parameters)

| Symbol | Meaning |
|---|---|
| $\mathcal H=\{1..h\}$ | working days |
| $\mathcal Q$ | qualifications |
| $\mathcal S$ | staff; $\mathcal Q_i^S\subseteq\mathcal Q$ skills of $i$, $\mathcal V_i^S\subseteq\mathcal H$ leave days of $i$ |
| $\mathcal J$ | projects; $\mathcal Q_j^J$ skills needed, $n_{j,k}$ person-days of skill $k$, $g_j$ gain, $d_j$ due date, $c_j$ daily penalty |
| $\mathcal A$ | eligible tuples $(i,j,k,t)$ with $k\in\mathcal Q_i^S\cap\mathcal Q_j^J$, $t\notin\mathcal V_i^S$ |

## 3. Decision variables

| Variable | Domain | Meaning |
|---|---|---|
| $X_{i,j,k,t}$ | $\{0,1\}$, $(i,j,k,t)\in\mathcal A$ | $i$ works on skill $k$ of project $j$ on day $t$ |
| $Y_j$ | $\{0,1\}$ | project $j$ is fully completed |
| $E_j$ | $\{0..h\}$ | last working day of $j$ |
| $B_j$ | $\{1..h\}$ | first working day of $j$ |
| $L_j$ | $\mathbb N$ | days of delay of $j$ |
| $D_j$ | $\{0..h\}$ | duration of $j$ (0 if not completed) |
| $P_{i,j}$ | $\{0,1\}$ | $i$ works at least one day on $j$ |
| $F_2, F_3$ | $\mathbb N$ | max projects per person, longest project |

The leave and qualification constraints of the course model ($X=0$ on leave days and for ineligible skills) are enforced by **not creating** those variables. On the large instance this leaves 3,939 binaries out of $6\cdot25\cdot10\cdot36=54{,}000$.

## 4. Constraints

| # | Constraint | Domain | Meaning |
|---|---|---|---|
| C1 | $\sum_{j,k} X_{i,j,k,t}\le 1$ | $\forall i,t$ | one task per person per day |
| C2-C3 | by construction of $\mathcal A$ | | leave and qualification |
| C4-C5 | $\sum_{i,t} X_{i,j,k,t} = n_{j,k}\,Y_j$ | $\forall j, k\in\mathcal Q_j^J$ | coverage, no over-staffing, no partial work |
| C6 | $t\,X_{i,j,k,t}\le E_j$ | $\forall (i,j,k,t)\in\mathcal A$ | end date |
| C7 | $E_j-d_j\le L_j$, $L_j\ge0$ | $\forall j$ | delay |
| C8 | $B_j\le t+h(1-X_{i,j,k,t})$ | $\forall (i,j,k,t)\in\mathcal A$ | start date |
| C9 | $X_{i,j,k,t}\le P_{i,j}$, $\sum_j P_{i,j}\le F_2$ | | multitasking |
| C10 | $D_j\ge E_j-B_j+1-(h+1)(1-Y_j)$, $D_j\le F_3$ | $\forall j$ | project duration |

The course model uses two inequalities, $Y_j n_{j,k}\le\sum X$ and $\sum X\le n_{j,k}$. We merge them into one equality (C4-C5), which forbids useless partial work on projects that are not completed. Every optimal solution of the course model can be turned into one of ours with the same profit by removing that partial work, so profit-optimality is unchanged. Partial work could only increase $f_2$ and $f_3$, so the merge also does no harm for the multi-objective model.

With only the single objective $f_1$, the model is exactly the course model (slides) and gives the same optimum (65 on the toy instance, 413 on the medium instance).

Implementation details (in `src/exact_solver.py`):
- **CP-SAT:** C6 and C8 are aggregated through $Z_{j,t}=\bigvee_{i,k}X_{i,j,k,t}$.
- **Valid cut:** $D_j\ge\max_k\lceil n_{j,k}/|\{i:k\in\mathcal Q^S_i\}|\rceil\cdot Y_j$.

## 5. Objectives

- $f_1=\sum_j (g_jY_j-c_jL_j)$, net profit. Maximise.
- $f_2=F_2=\max_i \sum_j P_{i,j}$, the most projects any collaborator works on. Minimise. This measures focus and context switching.
- $f_3=F_3=\max_j D_j$, the longest project from first to last working day. Minimise. This measures time-to-delivery.

We also report two indicators that are not optimised: the number of late projects, and the makespan $\max_j E_j$.

## 6. Computing the non-dominated set: ε-constraint

$f_2$ and $f_3$ take small integer values, so the exact ε-constraint method applies:

$$\max f_1 \quad \text{s.t. model},\; F_2\le\varepsilon_2,\; F_3\le\varepsilon_3$$

**Lexicographic tie-break.** Once the optimal profit $f_1^*$ is known, we solve a second phase that minimises $(h+1)F_2+F_3$ under $f_1\ge f_1^*$. With Gurobi we use its hierarchical multi-objective API instead. Without this step the method could return weakly dominated points.

We first tried a single weighted objective $W f_1-(h+1)F_2-F_3$. It is equivalent, but proving optimality took about 25× longer on the medium instance (110 s vs 4 s).

**Loops.** We loop over the two bounds as follows:

```
eps2 = |J|
while eps2 >= 0:
    eps3 = h ; maxF2 = -1
    while eps3 >= 0:
        q = argmax f1  s.t. F2 <= eps2, F3 <= eps3       (always feasible: empty plan)
        record q ; eps3 = F3(q) - 1 ; maxF2 = max(maxF2, F2(q))
    eps2 = maxF2 - 1
filter dominated / duplicate points
```

**Correctness.** Take any non-dominated point $p$ with $F_2(p)\le\varepsilon_2$. The inner loop reaches a $q$ with $f_1(q)\ge f_1(p)$ and $F_3(q)\le F_3(p)$. Either $q$ dominates or equals $p$, or $F_2(q)>F_2(p)$. In the second case $p$ is found later, because the next $\varepsilon_2$ is $\max F_2-1\ge F_2(p)$.

**Speed-ups that keep exactness:**
1. **Profit upper bound.** The optimum of $(\varepsilon_2,\varepsilon_3)$ is no larger than the proven bound of any solved $(\varepsilon_2',\varepsilon_3')$ with $\varepsilon_2' \ge \varepsilon_2$ and $\varepsilon_3' \ge \varepsilon_3$.
2. **Warm starts.** We pass the best already known solution that satisfies the current ε, taken from the heuristic archive or from previous optima.

When a sub-problem reaches its time limit, the point is the best one found, and the front is reported as **not proven** (`"exact": false` in `summary.json`).

## 7. Heuristic (`src/heuristic_solver.py`)

The heuristic is a randomised greedy with a Pareto archive.

**Greedy step.** It takes a project order and caps $(\varepsilon_2,\varepsilon_3)$. For each project in that order, it tries every start day $s$ and staffs the window $[s,s+\varepsilon_3-1]$ day by day, as many people in parallel as possible:
- scarcest skill first;
- prefer people already on the project, then the least versatile people;
- respect the $\varepsilon_2$ cap.

It keeps the start that finishes earliest. It drops the project if it cannot be completed or if $g_j-c_jL_j\le 0$.

**Multi-start.** The orders are: gain/workload, due date, then noisy gain/workload. For each order, every $(\varepsilon_2,\varepsilon_3)$ pair is tried. Dominated solutions are filtered out after each order. The heuristic finds solutions for all instances in seconds to a couple of minutes, and also serves as warm start for the exact method.

## 8. Validation and generator

- **Validator.** `src/solution.py` recomputes everything from the raw assignments ($Y, E, L$, objectives) and re-checks qualification, leave, uniqueness and over-staffing. Every reported solution passes it, and `run_experiments.py` asserts this.
- **Instance generator.** `src/instance_generator.py` has these controls: number of staff, projects, horizon and skills; *load* = demand / capacity; vacation rate (contiguous blocks); due dates; and gains roughly proportional to project size.
- **Tests.** `tests/test_models.py` checks:
  - the toy optimum is 65;
  - the toy front is exact and non-dominated;
  - heuristic solutions are feasible;
  - the validator catches violations;
  - a generated instance can be solved.

## 9. Results

All runs used OR-Tools CP-SAT (8 workers) on a Windows laptop with 8 logical cores. Time limit per ε sub-problem (phase 1):
- toy and medium: 90 s;
- large: 30 s;
- generated instances: 20 s.

Load is demand divided by capacity, in person-days. C(A,B) is the share of B's points that are weakly dominated by a point of A (Zitzler coverage).

| Instance | \|S\| | \|J\| | h | X vars | load | best profit | exact pts | exact time (s) | proven | heur pts | heur time (s) | C(exact,heur) | C(heur,exact) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| toy | 3 | 5 | 5 | 90 | 1.08 | **65** | 10 | 1.4 | yes | 9 | 0.05 | 1.0 | 0.40 |
| medium | 5 | 15 | 22 | 1298 | 1.32 | **413** | 44 | 2169 | no (13/66 sub-problems at limit) | 36 | 41 | 1.0 | 0.11 |
| large | 6 | 25 | 36 | 3939 | 1.41 | **811** | 79 | 4039 | no (94/147 at limit) | 78 | 636* | 1.0 | 0.08 |
| gen_s3_j6_h8 | 3 | 6 | 8 | 105 | 1.38 | 92 | 8 | 3.7 | yes | 9 | 0.2 | 1.0 | 0.13 |
| gen_s4_j10_h12 | 4 | 10 | 12 | 550 | 1.21 | 172 | 32 | 124 | yes | 18 | 3.6 | 1.0 | 0.16 |
| gen_s5_j12_h15 | 5 | 12 | 15 | 841 | 1.52 | 229 | 39 | 320 | no | 25 | 9.5 | 1.0 | 0.08 |
| gen_s5_j15_h20 | 5 | 15 | 20 | 1112 | 1.44 | 345 | 41 | 384 | no | 38 | 26 | 1.0 | 0.15 |
| gen_s6_j20_h25 | 6 | 20 | 25 | 1580 | 1.40 | 409 | 57 | 976 | no | 46 | 93 | 1.0 | 0.12 |
| gen_s8_j30_h30 | 8 | 30 | 30 | 4060 | 1.44 | 616 (heur.) | – | – | – | 66 | 100 | – | – |

\* The large run shared the CPU with the medium and generated runs, so its heuristic time is inflated.

**Single-objective optimum.** The best profit of the front is the profit-only optimum: 65 on toy and 413 on medium (both proven optimal). On large, 811 is the best found within the limit; the heuristic alone reaches 742.

**Exact vs heuristic.** The ε-constraint front covers 100% of every heuristic front. The heuristic covers 8-40% of the exact front, and its best profit is 6-9% below the exact one on medium and large. The heuristic is still useful: it gives a good front in seconds, and it warm-starts the exact method.

**Scalability.** The front is fully proven up to about 550 X variables (10 projects, 12 days). Beyond that, some ε sub-problems stop at the time limit, so those fronts are high-quality approximations rather than proven fronts (`"exact": false`). Proving optimality is hardest when $\varepsilon_3$ (maximum project duration) is moderately tight.

**Trade-offs (what the CEO should know)**

| | toy | medium | large |
|---|---|---|---|
| max profit | 65 | 413 | 811 |
| best profit with **no late project** | 65 (100%) | 385 (93%) | 775 (96%) |
| best profit with f2 ≤ 2 projects per person | 65 (100%) | 326 (79%) | 517 (64%) |
| best profit with f2 = 1 | 42 (65%) | 194 (47%) | 290 (36%) |
| compromise (closest to ideal) | 55 · f2=2 · f3=2 | 322 · f2=3 · f3=5 | 605 · f2=4 · f3=8 |

- **Lateness costs little to remove.** Removing all lateness costs only 4-7% of profit.
- **Focus is expensive.** Asking each collaborator to work on only one or two projects is the costly constraint. Skills are spread thinly, so scarce qualifications have to be shared across projects.
- **Very short projects destroy profit.** Large projects need several people over several days, so a very small $f_3$ forces them to be dropped.

## 10. Visualisations

- **Objective space:**
  - `results/<instance>/pareto.png` shows a 3-D view and the three 2-D projections, exact vs heuristic.
  - `results/<instance>/pareto.html` is an interactive Plotly 3-D view. Hovering a point shows its completed projects.
- **Decision space:** Gantt charts with staff as rows and days as columns. Each cell shows the project and skill. Leave days are hatched and due dates are dotted lines.
  - `gantt_max_profit.png`: the max-profit schedule;
  - `gantt_compromise.png`: the point closest to the ideal point, with normalised objectives;
  - `gantt_min_multitasking.png`: the min-$f_2$ schedule.
