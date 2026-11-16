"""Load a CompuOpti JSON instance into plain Python structures.

Notation follows PROJECT_SPECIFICATIONS.md:
    H = {1..h}, Q (qualifications), S (staff), J (jobs/projects)
    Q_i^S, V_i^S for staff;  Q_j^J, n_{j,k}, g_j, d_j, c_j for projects.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Staff:
    name: str
    qualifications: set[str]
    vacations: set[int]


@dataclass
class Job:
    name: str
    gain: int
    due_date: int
    daily_penalty: int
    requirements: dict[str, int]  # k -> n_{j,k}

    @property
    def total_workload(self) -> int:
        return sum(self.requirements.values())


@dataclass
class Instance:
    name: str
    horizon: int
    qualifications: list[str]
    staff: list[Staff]
    jobs: list[Job]
    _eligible: list[tuple[int, int, str, int]] | None = field(default=None, repr=False)

    @property
    def days(self) -> range:
        return range(1, self.horizon + 1)

    def eligible_tuples(self) -> list[tuple[int, int, str, int]]:
        """All (i, j, k, t) for which X_{i,j,k,t} may be 1.

        Constraints 2 (leave) and 3 (qualification eligibility) are enforced here
        by *not creating* the forbidden variables (sparse model).
        """
        if self._eligible is None:
            out = []
            for i, s in enumerate(self.staff):
                for j, job in enumerate(self.jobs):
                    for k in job.requirements:
                        if k not in s.qualifications:
                            continue
                        for t in self.days:
                            if t not in s.vacations:
                                out.append((i, j, k, t))
            self._eligible = out
        return self._eligible

    def summary(self) -> dict:
        return {
            "instance": self.name,
            "horizon": self.horizon,
            "n_qualifications": len(self.qualifications),
            "n_staff": len(self.staff),
            "n_jobs": len(self.jobs),
            "total_gain": sum(j.gain for j in self.jobs),
            "total_demand_person_days": sum(j.total_workload for j in self.jobs),
            "total_capacity_person_days": sum(
                self.horizon - len(s.vacations) for s in self.staff
            ),
            "n_x_variables": len(self.eligible_tuples()),
        }


def instance_from_dict(data: dict, name: str = "instance") -> Instance:
    staff = [
        Staff(s["name"], set(s["qualifications"]), set(int(v) for v in s["vacations"]))
        for s in data["staff"]
    ]
    jobs = [
        Job(
            j["name"],
            int(j["gain"]),
            int(j["due_date"]),
            int(j["daily_penalty"]),
            {k: int(v) for k, v in j["working_days_per_qualification"].items()},
        )
        for j in data["jobs"]
    ]
    return Instance(name, int(data["horizon"]), list(data["qualifications"]), staff, jobs)


def load_instance(path: str | Path) -> Instance:
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return instance_from_dict(data, name=path.stem)


def instance_to_dict(inst: Instance) -> dict:
    return {
        "horizon": inst.horizon,
        "qualifications": inst.qualifications,
        "staff": [
            {"name": s.name, "qualifications": sorted(s.qualifications), "vacations": sorted(s.vacations)}
            for s in inst.staff
        ],
        "jobs": [
            {
                "name": j.name,
                "gain": j.gain,
                "due_date": j.due_date,
                "daily_penalty": j.daily_penalty,
                "working_days_per_qualification": j.requirements,
            }
            for j in inst.jobs
        ],
    }
