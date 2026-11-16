"""Random instance generator (same JSON schema as the course instances).

The generator controls the *load ratio* = total demand / total capacity, so
that instances are neither trivial (everything fits) nor hopeless.

Usage:
    python instance_generator.py --staff 6 --jobs 20 --horizon 30 --quals 8 \
        --load 1.3 --seed 1 --out ../Datasets-generated/gen_s6_j20.json
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

NAMES = ["Olivia", "Liam", "Emma", "Noah", "Amelia", "Oliver", "Ava", "Elijah",
         "Sophia", "Lucas", "Mia", "Levi", "Isabella", "Mateo", "Luna", "Ezra"]


def generate(n_staff: int = 5, n_jobs: int = 15, horizon: int = 22, n_quals: int = 8,
             load: float = 1.3, vacation_rate: float = 0.08, seed: int = 0,
             daily_penalty: int = 3) -> dict:
    rng = random.Random(seed)
    quals = [chr(ord("A") + q) for q in range(n_quals)]

    # Staff: 2..4 qualifications each, every qualification held by >= 1 person.
    staff = []
    for s in range(n_staff):
        qs = rng.sample(quals, k=rng.randint(2, min(4, n_quals)))
        staff.append({"name": NAMES[s % len(NAMES)] + ("" if s < len(NAMES) else str(s)),
                      "qualifications": qs, "vacations": []})
    for q in quals:
        if not any(q in s["qualifications"] for s in staff):
            rng.choice(staff)["qualifications"].append(q)

    # Vacations: contiguous blocks (more realistic than isolated days).
    for s in staff:
        n_vac = int(round(rng.uniform(0, 2 * vacation_rate) * horizon))
        if n_vac:
            start = rng.randint(1, max(1, horizon - n_vac + 1))
            s["vacations"] = list(range(start, min(horizon, start + n_vac - 1) + 1))

    capacity = sum(horizon - len(s["vacations"]) for s in staff)
    target_demand = load * capacity
    mean_job = target_demand / n_jobs

    jobs = []
    for j in range(n_jobs):
        nq = rng.randint(1, min(3, n_quals))
        qs = rng.sample(quals, k=nq)
        size = max(nq, int(round(rng.uniform(0.5, 1.5) * mean_job)))
        # split `size` person-days among the qualifications (each >= 1)
        cuts = sorted(rng.sample(range(1, size), nq - 1)) if nq > 1 else []
        parts = [b - a for a, b in zip([0] + cuts, cuts + [size])]
        req = {q: p for q, p in zip(qs, parts)}
        # Gain roughly proportional to size with noise -> heterogeneous profitability.
        gain = int(5 * round(size * rng.uniform(2.0, 5.0) / 5)) or 5
        # Due date: somewhere between "tight" and "end of horizon".
        due = rng.randint(max(2, min(horizon, size // 2)), horizon)
        jobs.append({"name": f"Job{j + 1}", "gain": gain, "due_date": due,
                     "daily_penalty": daily_penalty,
                     "working_days_per_qualification": req})

    return {"horizon": horizon, "qualifications": quals, "staff": staff, "jobs": jobs}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--staff", type=int, default=5)
    p.add_argument("--jobs", type=int, default=15)
    p.add_argument("--horizon", type=int, default=22)
    p.add_argument("--quals", type=int, default=8)
    p.add_argument("--load", type=float, default=1.3)
    p.add_argument("--vacation-rate", type=float, default=0.08)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=str, required=True)
    a = p.parse_args()
    data = generate(a.staff, a.jobs, a.horizon, a.quals, a.load, a.vacation_rate, a.seed)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print("written", a.out)


if __name__ == "__main__":
    main()
