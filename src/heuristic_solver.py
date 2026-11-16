"""Fast multi-objective heuristic (randomised greedy + Pareto archive).

Constructive greedy for a given project order and caps (eps2 = max projects
per staff, eps3 = max project duration):
  for each project j in order:
      for every start day s, try to staff j inside the window [s, s+eps3-1]
      day by day (as many people in parallel as possible -> short, early
      projects), respecting vacations, one task per staff-day, qualifications
      and the eps2 cap.  Keep the start that finishes earliest (ties: latest
      start = shortest duration).  Skip j if it cannot be completed or if its
      net gain g_j - c_j L_j <= 0.

The multi-start loop draws random project orders (biased towards high
gain / workload) for every (eps2, eps3) cap pair and keeps a Pareto archive.
It returns an *approximation* of the non-dominated set in a few seconds, even
where the exact epsilon-constraint method is slow.
"""
from __future__ import annotations

import random
import time

from data_loader import Instance
from solution import Solution, non_dominated, objective_vector


def greedy(inst: Instance, order: list[int], eps2: int, eps3: int) -> Solution:
    h = inst.horizon
    busy: dict[tuple[int, int], bool] = {}
    staff_jobs: list[set[int]] = [set() for _ in inst.staff]
    assignments: list[tuple[int, int, str, int]] = []

    def try_window(j: int, s: int):
        job = inst.jobs[j]
        need = dict(job.requirements)
        plan = []
        newly = set()
        e = min(h, s + eps3 - 1)
        for t in range(s, e + 1):
            if not any(need.values()):
                break
            used_today = set()
            # scarce qualifications first
            for k in sorted((k for k in need if need[k] > 0),
                            key=lambda k: sum(k in st.qualifications for st in inst.staff)):
                cands = []
                for i, st in enumerate(inst.staff):
                    if (k not in st.qualifications or t in st.vacations or busy.get((i, t))
                            or i in used_today):
                        continue
                    on_job = j in staff_jobs[i] or i in newly
                    if not on_job and len(staff_jobs[i]) + 1 > eps2:
                        continue
                    cands.append((not on_job, len(st.qualifications), i))
                for _, _, i in sorted(cands)[: need[k]]:
                    plan.append((i, j, k, t))
                    used_today.add(i)
                    newly.add(i)
                    need[k] -= 1
        if any(need.values()):
            return None
        return plan

    for j in order:
        job = inst.jobs[j]
        if job.total_workload == 0:
            continue
        best = None
        for s in range(1, h + 1):
            if best is not None and s > best[0][0]:
                break  # a later start cannot finish earlier
            plan = try_window(j, s)
            if plan is None:
                continue
            E = max(a[3] for a in plan)
            key = (E, -s)
            if best is None or key < best[0]:
                best = (key, plan)
        if best is None:
            continue
        plan = best[1]
        E = best[0][0]
        if job.gain - job.daily_penalty * max(0, E - job.due_date) <= 0:
            continue
        for (i, jj, k, t) in plan:
            busy[(i, t)] = True
            staff_jobs[i].add(jj)
        assignments.extend(plan)
    return Solution(assignments, {"backend": "heuristic", "eps2": eps2, "eps3": eps3})


def heuristic_front(inst: Instance, n_iter: int = 30, seed: int = 0,
                    time_budget: float | None = None) -> tuple[list[Solution], dict]:
    rng = random.Random(seed)
    t0 = time.perf_counter()
    m = len(inst.jobs)
    ratio = [job.gain / max(1, job.total_workload) for job in inst.jobs]
    archive: list[Solution] = []
    n_runs = 0
    eps2_values = range(1, min(m, inst.horizon) + 1)
    eps3_values = range(1, inst.horizon + 1)
    for it in range(n_iter):
        if it == 0:
            order = sorted(range(m), key=lambda j: -ratio[j])
        elif it == 1:
            order = sorted(range(m), key=lambda j: (inst.jobs[j].due_date, -ratio[j]))
        else:  # noisy ratio ordering (GRASP-like)
            order = sorted(range(m), key=lambda j: -ratio[j] * rng.uniform(0.5, 1.5))
        for e2 in eps2_values:
            for e3 in eps3_values:
                sol = greedy(inst, order, e2, e3)
                n_runs += 1
                archive.append(sol)
        archive = non_dominated(archive, key=lambda s: objective_vector(inst, s))
        if time_budget and time.perf_counter() - t0 > time_budget:
            break
    archive.sort(key=lambda s: objective_vector(inst, s), reverse=True)
    return archive, {"n_points": len(archive), "n_greedy_runs": n_runs,
                     "total_time_s": round(time.perf_counter() - t0, 2), "exact": False,
                     "backend": "heuristic"}
