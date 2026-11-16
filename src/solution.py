"""Solution representation, solver-independent evaluation and validation.

A solution is just the list of active assignments (i, j, k, t), i.e. the
tuples with X_{i,j,k,t} = 1.  Everything else (Y, E, L, objectives) is
recomputed from it, so the validator never trusts a solver's own numbers.

Objectives (see docs/REPORT.md):
    f1  profit            = sum_{j completed} (g_j - c_j * L_j)        (max)
    f2  max_projects      = max_i |{j : i works on j}|                  (min)
    f3  max_duration      = max_{j completed} (E_j - B_j + 1)           (min)
Indicators (not optimised, reported):
    n_completed, n_late, total_tardiness, makespan = max_j E_j
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from data_loader import Instance


@dataclass
class Solution:
    assignments: list[tuple[int, int, str, int]]
    meta: dict = field(default_factory=dict)

    def to_dict(self, inst: Instance) -> dict:
        return {
            "assignments": [
                {"staff": inst.staff[i].name, "job": inst.jobs[j].name, "qualification": k, "day": t}
                for (i, j, k, t) in sorted(self.assignments, key=lambda a: (a[0], a[3]))
            ],
            "objectives": evaluate(inst, self),
            "meta": self.meta,
        }


def evaluate(inst: Instance, sol: Solution) -> dict:
    done = defaultdict(int)          # (j,k) -> person-days delivered
    days_of_job = defaultdict(list)  # j -> days worked
    jobs_of_staff = defaultdict(set)
    for (i, j, k, t) in sol.assignments:
        done[(j, k)] += 1
        days_of_job[j].append(t)
        jobs_of_staff[i].add(j)

    completed = [
        j for j, job in enumerate(inst.jobs)
        if all(done[(j, k)] >= n for k, n in job.requirements.items())
    ]
    profit = 0
    n_late = 0
    tard = 0
    durations = []
    ends = []
    for j in completed:
        job = inst.jobs[j]
        E = max(days_of_job[j]) if days_of_job[j] else 0
        B = min(days_of_job[j]) if days_of_job[j] else 0
        L = max(0, E - job.due_date)
        profit += job.gain - job.daily_penalty * L
        n_late += L > 0
        tard += L
        durations.append(E - B + 1 if days_of_job[j] else 0)
        ends.append(E)
    return {
        "profit": profit,
        "max_projects_per_staff": max((len(v) for v in jobs_of_staff.values()), default=0),
        "max_duration": max(durations, default=0),
        "n_completed": len(completed),
        "completed": [inst.jobs[j].name for j in completed],
        "n_late": n_late,
        "total_tardiness": tard,
        "makespan": max(ends, default=0),
    }


def objective_vector(inst: Instance, sol: Solution) -> tuple[int, int, int]:
    e = evaluate(inst, sol)
    return e["profit"], e["max_projects_per_staff"], e["max_duration"]


def validate(inst: Instance, sol: Solution) -> list[str]:
    """Return the list of violated constraints (empty list == feasible)."""
    errors = []
    seen = defaultdict(list)
    done = defaultdict(int)
    for (i, j, k, t) in sol.assignments:
        s, job = inst.staff[i], inst.jobs[j]
        if not 1 <= t <= inst.horizon:
            errors.append(f"day {t} outside horizon for {s.name}")
        if t in s.vacations:
            errors.append(f"{s.name} works on vacation day {t}")
        if k not in s.qualifications:
            errors.append(f"{s.name} lacks qualification {k} (day {t}, {job.name})")
        if k not in job.requirements:
            errors.append(f"{job.name} does not require {k} (day {t}, {s.name})")
        seen[(i, t)].append((j, k))
        done[(j, k)] += 1
    for (i, t), lst in seen.items():
        if len(lst) > 1:
            errors.append(f"{inst.staff[i].name} has {len(lst)} assignments on day {t}")
    for (j, k), v in done.items():
        n = inst.jobs[j].requirements.get(k, 0)
        if v > n:
            errors.append(f"{inst.jobs[j].name}/{k}: {v} person-days > required {n}")
    return errors


def dominates(a: tuple, b: tuple) -> bool:
    """a, b = (profit, f2, f3); profit maximised, f2/f3 minimised."""
    better_eq = a[0] >= b[0] and a[1] <= b[1] and a[2] <= b[2]
    return better_eq and a != b


def non_dominated(points: list, key=lambda p: p) -> list:
    """Filter a list down to its non-dominated elements (keeps one per vector)."""
    keyed = [(key(p), p) for p in points]
    uniq = {}
    for v, p in keyed:
        uniq.setdefault(v, p)
    vs = list(uniq)
    return [uniq[v] for v in vs if not any(dominates(w, v) for w in vs)]
