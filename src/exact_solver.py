"""Exact MILP / CP models and the epsilon-constraint Pareto front.

Two interchangeable back-ends implement the *same* model:
  * "cpsat"  : Google OR-Tools CP-SAT (free, default, solves all 3 instances)
  * "gurobi" : gurobipy (needs a full academic licence for medium/large;
               the pip "restricted" licence is limited to 2000 vars/constraints)

Model (indices i in S, j in J, k in Q_j^J, t in H) -- see docs/REPORT.md
    X_{ijkt} in {0,1}   only created when k in Q_i^S, k in Q_j^J, t not in V_i^S
    Y_j in {0,1}        project j fully completed
    E_j, B_j            last / first working day of project j
    L_j >= 0            days of delay of project j
    P_{ij} in {0,1}     staff i works at least one day on project j
    D_j                 duration of project j (0 if not completed)
    F2 = max_i sum_j P_ij ,  F3 = max_j D_j

    (C1) sum_{j,k} X_{ijkt} <= 1                       for all i, t
    (C2/C3) leave and qualification: by sparse variable creation
    (C4+C5) sum_{i,t} X_{ijkt} = n_{jk} * Y_j           for all j, k in Q_j^J
    (C6) t * X_{ijkt} <= E_j                            for all eligible (i,j,k,t)
    (C7) E_j - d_j <= L_j
    (C8) B_j <= t + h (1 - X_{ijkt})
    (C9) X_{ijkt} <= P_{ij} ;  sum_j P_{ij} <= F2
    (C10) D_j >= E_j - B_j + 1 - (h+1)(1 - Y_j) ;  D_j <= F3
    epsilon constraints:  F2 <= eps2 , F3 <= eps3

Objective: lexicographic  max f1, then min (h+1) F2 + F3, solved in two
phases (CP-SAT) or with Gurobi's hierarchical objectives.  A single weighted
objective W*f1 - (h+1)F2 - F3 is equivalent but was ~25x slower to prove on
the medium instance (110 s vs 4 s).  The tie-break removes weakly
non-dominated points; correctness of the front only needs phase 1 optimal.
"""
from __future__ import annotations

import time
from collections import defaultdict

from data_loader import Instance
from solution import Solution, evaluate, non_dominated, objective_vector


# --------------------------------------------------------------------------- #
# CP-SAT back-end
# --------------------------------------------------------------------------- #
def solve_cpsat(inst: Instance, eps2: int | None = None, eps3: int | None = None,
                time_limit: float = 60.0, workers: int = 8, hint: Solution | None = None,
                lexicographic: bool = True, profit_ub: int | None = None) -> Solution | None:
    from ortools.sat.python import cp_model

    h, m = inst.horizon, len(inst.jobs)
    md = cp_model.CpModel()
    tuples = inst.eligible_tuples()
    X = {a: md.NewBoolVar("x_%d_%d_%s_%d" % a) for a in tuples}
    Y = [md.NewBoolVar(f"y_{j}") for j in range(m)]
    E = [md.NewIntVar(0, h, f"E_{j}") for j in range(m)]
    B = [md.NewIntVar(1, h, f"B_{j}") for j in range(m)]
    L = [md.NewIntVar(0, h, f"L_{j}") for j in range(m)]
    D = [md.NewIntVar(0, h, f"D_{j}") for j in range(m)]
    F2 = md.NewIntVar(0, m, "F2")
    F3 = md.NewIntVar(0, h, "F3")

    by_it, by_jk, by_ij, by_jt = (defaultdict(list) for _ in range(4))
    for a, x in X.items():
        i, j, k, t = a
        by_it[(i, t)].append(x)
        by_jk[(j, k)].append(x)
        by_ij[(i, j)].append(x)
        by_jt[(j, t)].append(x)
    # Z_{jt} = 1 if somebody works on j on day t (aggregates C6/C8: far fewer
    # reified constraints than one per X).
    for (j, t), xs in by_jt.items():
        z = md.NewBoolVar(f"z_{j}_{t}")
        for x in xs:
            md.AddImplication(x, z)
        md.AddBoolOr(xs).OnlyEnforceIf(z)
        md.Add(E[j] >= t).OnlyEnforceIf(z)                    # C6
        md.Add(B[j] <= t).OnlyEnforceIf(z)                    # C8
    for xs in by_it.values():
        md.AddAtMostOne(xs)                                   # C1
    for j, job in enumerate(inst.jobs):
        for k, n in job.requirements.items():
            md.Add(sum(by_jk[(j, k)]) == n * Y[j])            # C4 + C5
        md.Add(L[j] >= E[j] - job.due_date)                   # C7
        md.Add(D[j] >= E[j] - B[j] + 1).OnlyEnforceIf(Y[j])   # C10
        md.Add(D[j] <= F3)
        # valid cut: a project cannot last less than its busiest qualification
        # divided by the number of people holding it
        lb = max(-(-n // max(1, sum(k in s.qualifications for s in inst.staff)))
                 for k, n in job.requirements.items())
        md.Add(D[j] >= lb).OnlyEnforceIf(Y[j])
        md.Add(E[j] >= B[j] + lb - 1).OnlyEnforceIf(Y[j])
    P = {}
    for (i, j), xs in by_ij.items():
        P[(i, j)] = md.NewBoolVar(f"p_{i}_{j}")
        for x in xs:
            md.AddImplication(x, P[(i, j)])                   # C9
    for i in range(len(inst.staff)):
        ps = [P[(i, j)] for j in range(m) if (i, j) in P]
        if ps:
            md.Add(sum(ps) <= F2)
    if eps2 is not None:
        md.Add(F2 <= eps2)
    if eps3 is not None:
        md.Add(F3 <= eps3)

    profit = sum(job.gain * Y[j] - job.daily_penalty * L[j] for j, job in enumerate(inst.jobs))
    if profit_ub is not None:  # valid bound inherited from a less constrained sub-problem
        md.Add(profit <= profit_ub)

    def set_hint(active_set):
        md.ClearHints()
        for a, x in X.items():
            md.AddHint(x, 1 if a in active_set else 0)

    if hint is not None:
        set_hint(set(hint.assignments))

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = workers
    t0 = time.perf_counter()

    # Phase 1: max profit (this phase must be proven optimal for exactness).
    md.Maximize(profit)
    solver.parameters.max_time_in_seconds = time_limit
    status = solver.Solve(md)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    status1 = status
    best_profit = int(round(solver.ObjectiveValue()))
    bound = int(solver.BestObjectiveBound() + 1e-6)
    active = [a for a, x in X.items() if solver.BooleanValue(x)]

    # Phase 2 (lexicographic tie-break): at profit = f1*, min (h+1)*F2 + F3.
    # Any feasible answer is valid; it only removes weakly dominated points.
    if lexicographic:
        set_hint(set(active))
        md.Add(profit >= best_profit)
        md.Minimize((h + 1) * F2 + F3)
        solver.parameters.max_time_in_seconds = max(5.0, time_limit / 4)
        status2 = solver.Solve(md)
        if status2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            active = [a for a, x in X.items() if solver.BooleanValue(x)]
    dt = time.perf_counter() - t0
    return Solution(
        active,
        {
            "backend": "cpsat",
            "status": "optimal" if status1 == cp_model.OPTIMAL else "feasible (time limit)",
            "profit_bound": bound,
            "time_s": round(dt, 3),
            "eps2": eps2, "eps3": eps3,
            "n_vars": len(md.Proto().variables),
            "n_constraints": len(md.Proto().constraints),
        },
    )


# --------------------------------------------------------------------------- #
# Gurobi back-end (same model, linearised big-M form as in the course slides)
# --------------------------------------------------------------------------- #
def solve_gurobi(inst: Instance, eps2: int | None = None, eps3: int | None = None,
                 time_limit: float = 60.0, hint: Solution | None = None,
                 lexicographic: bool = True, verbose: bool = False,
                 profit_ub: int | None = None) -> Solution | None:
    import gurobipy as gp
    from gurobipy import GRB, quicksum

    h, m = inst.horizon, len(inst.jobs)
    md = gp.Model("CompuOpti_Staffing")
    md.Params.OutputFlag = 1 if verbose else 0
    md.Params.TimeLimit = time_limit
    tuples = inst.eligible_tuples()
    X = md.addVars(tuples, vtype=GRB.BINARY, name="X")
    Y = md.addVars(m, vtype=GRB.BINARY, name="Y")
    E = md.addVars(m, lb=0, ub=h, vtype=GRB.INTEGER, name="E")
    B = md.addVars(m, lb=1, ub=h, vtype=GRB.INTEGER, name="B")
    L = md.addVars(m, lb=0, ub=h, vtype=GRB.INTEGER, name="L")
    D = md.addVars(m, lb=0, ub=h, vtype=GRB.INTEGER, name="D")
    F2 = md.addVar(lb=0, ub=m, vtype=GRB.INTEGER, name="F2")
    F3 = md.addVar(lb=0, ub=h, vtype=GRB.INTEGER, name="F3")

    by_it, by_jk, by_ij = defaultdict(list), defaultdict(list), defaultdict(list)
    for a in tuples:
        i, j, k, t = a
        by_it[(i, t)].append(a)
        by_jk[(j, k)].append(a)
        by_ij[(i, j)].append(a)
        md.addConstr(t * X[a] <= E[j], name="C6")
        md.addConstr(B[j] <= t + h * (1 - X[a]), name="C8")
    for key, lst in by_it.items():
        md.addConstr(quicksum(X[a] for a in lst) <= 1, name="C1")
    for j, job in enumerate(inst.jobs):
        for k, n in job.requirements.items():
            md.addConstr(quicksum(X[a] for a in by_jk[(j, k)]) == n * Y[j], name="C4C5")
        md.addConstr(E[j] - job.due_date <= L[j], name="C7")
        md.addConstr(D[j] >= E[j] - B[j] + 1 - (h + 1) * (1 - Y[j]), name="C10")
        md.addConstr(D[j] <= F3)
    P = md.addVars(list(by_ij), vtype=GRB.BINARY, name="P")
    for key, lst in by_ij.items():
        for a in lst:
            md.addConstr(X[a] <= P[key], name="C9")
    for i in range(len(inst.staff)):
        ps = [P[(i, j)] for j in range(m) if (i, j) in by_ij]
        if ps:
            md.addConstr(quicksum(ps) <= F2)
    if eps2 is not None:
        md.addConstr(F2 <= eps2, name="eps2")
    if eps3 is not None:
        md.addConstr(F3 <= eps3, name="eps3")
    profit = quicksum(job.gain * Y[j] - job.daily_penalty * L[j] for j, job in enumerate(inst.jobs))
    if profit_ub is not None:
        md.addConstr(profit <= profit_ub, name="profit_ub")
    md.ModelSense = GRB.MAXIMIZE
    # Gurobi native hierarchical (lexicographic) multi-objective.
    md.setObjectiveN(profit, index=0, priority=2, name="profit")
    if lexicographic:
        md.setObjectiveN(-((h + 1) * F2 + F3), index=1, priority=1, name="tiebreak")
    if hint is not None:
        active = set(hint.assignments)
        for a in tuples:
            X[a].Start = 1 if a in active else 0

    t0 = time.perf_counter()
    md.optimize()
    dt = time.perf_counter() - t0
    if md.SolCount == 0:
        return None
    optimal = md.Status == GRB.OPTIMAL
    return Solution(
        [a for a in tuples if X[a].X > 0.5],
        {
            "backend": "gurobi",
            "status": "optimal" if optimal else "feasible (time limit)",
            "profit_bound": None if not optimal else int(round(sum(
                job.gain * Y[j].X - job.daily_penalty * L[j].X for j, job in enumerate(inst.jobs)))),
            "time_s": round(dt, 3),
            "eps2": eps2, "eps3": eps3,
            "n_vars": md.NumVars, "n_constraints": md.NumConstrs,
        },
    )


def solve(inst: Instance, backend: str = "cpsat", **kw) -> Solution | None:
    return (solve_gurobi if backend == "gurobi" else solve_cpsat)(inst, **kw)


# --------------------------------------------------------------------------- #
# Epsilon-constraint method (3 objectives: max f1, min F2, min F3)
# --------------------------------------------------------------------------- #
def pareto_front(inst: Instance, backend: str = "cpsat", time_limit: float = 60.0,
                 log=print, seeds: list[Solution] | None = None) -> tuple[list[Solution], dict]:
    """Exact non-dominated set by nested epsilon-constraint.

    Outer loop on eps2 (max projects per staff), inner loop on eps3 (max
    project duration).  After each optimum q:  eps3 <- F3(q) - 1.  After the
    inner loop: eps2 <- max F2 found in that inner loop - 1.  The empty
    schedule (profit 0, F2 = F3 = 0) is always feasible, so every
    sub-problem is feasible and the loops stop when an epsilon becomes < 0.

    Speed-ups (do not affect exactness):
      * profit upper bound: the optimum of (e2, e3) is <= the proven bound of
        any already-solved (e2', e3') with e2' >= e2 and e3' >= e3;
      * warm start: best known solution (previous optimum or heuristic seed)
        satisfying the current epsilons is passed as a hint / MIP start.
    """
    t_start = time.perf_counter()
    found: list[Solution] = []
    pool: list[tuple[tuple, Solution]] = [(objective_vector(inst, s), s) for s in (seeds or [])]
    bounds: dict[tuple[int, int], int] = {}
    n_solves = 0
    all_optimal = True
    eps2 = len(inst.jobs)
    while eps2 >= 0:
        eps3 = inst.horizon
        max_f2_inner = -1
        while eps3 >= 0:
            ub = min((b for (e2, e3), b in bounds.items() if e2 >= eps2 and e3 >= eps3),
                     default=None)
            ok = [(v, s) for v, s in pool if v[1] <= eps2 and v[2] <= eps3]
            hint = max(ok, key=lambda vs: vs[0][0])[1] if ok else None
            sol = solve(inst, backend=backend, eps2=eps2, eps3=eps3,
                        time_limit=time_limit, hint=hint, profit_ub=ub)
            n_solves += 1
            if sol is None:
                break
            if sol.meta.get("profit_bound") is not None:
                bounds[(eps2, eps3)] = sol.meta["profit_bound"]
            all_optimal &= sol.meta["status"] == "optimal"
            f = objective_vector(inst, sol)
            log(f"  eps2={eps2:>2} eps3={eps3:>2} -> profit={f[0]:>4} F2={f[1]} F3={f[2]}"
                f"  [{sol.meta['status']}, {sol.meta['time_s']}s]")
            found.append(sol)
            pool.append((f, sol))
            max_f2_inner = max(max_f2_inner, f[1])
            eps3 = f[2] - 1
        eps2 = max_f2_inner - 1
    front = non_dominated(found, key=lambda s: objective_vector(inst, s))
    front.sort(key=lambda s: objective_vector(inst, s), reverse=True)
    stats = {
        "n_solves": n_solves,
        "n_points": len(front),
        "total_time_s": round(time.perf_counter() - t_start, 2),
        "exact": all_optimal,
        "backend": backend,
    }
    return front, stats


if __name__ == "__main__":
    import sys
    from data_loader import load_instance

    inst = load_instance(sys.argv[1])
    sol = solve(inst, backend=sys.argv[2] if len(sys.argv) > 2 else "cpsat", time_limit=120)
    print(sol.meta)
    print(evaluate(inst, sol))
