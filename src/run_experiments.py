"""Run every method on every instance and save results + figures.

    python run_experiments.py --instances toy medium --time-limit 120
    python run_experiments.py --instances large --time-limit 20
    python run_experiments.py --generated          # generator benchmark

Outputs (in ../results/<instance>/):
    front_exact.json, front_heuristic.json   non-dominated solutions + objectives
    pareto.png, pareto.html                  objective space
    gantt_*.png                              decision space (selected solutions)
    summary.json                             timings, sizes, front statistics
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from data_loader import instance_from_dict, load_instance  # noqa: E402
from exact_solver import pareto_front  # noqa: E402
from heuristic_solver import heuristic_front  # noqa: E402
from instance_generator import generate  # noqa: E402
from solution import evaluate, objective_vector, validate  # noqa: E402
from visualization import plot_gantt, plot_pareto, plot_pareto_interactive  # noqa: E402


def coverage(a, b, inst):
    """C(A,B): share of B weakly dominated by some point of A (Zitzler)."""
    va = [objective_vector(inst, s) for s in a]
    vb = [objective_vector(inst, s) for s in b]
    if not vb:
        return 0.0
    hit = sum(any(x[0] >= y[0] and x[1] <= y[1] and x[2] <= y[2] for x in va) for y in vb)
    return round(hit / len(vb), 3)


def run(inst, out: Path, time_limit: float, heur_iters: int, skip_exact: bool = False):
    out.mkdir(parents=True, exist_ok=True)
    log_f = open(out / "log.txt", "w", encoding="utf-8")

    def log(msg):
        print(msg, flush=True)
        log_f.write(msg + "\n")
        log_f.flush()

    summ = {"instance": inst.summary()}
    log(f"=== {inst.name}: {summ['instance']}")

    heur, hst = heuristic_front(inst, n_iter=heur_iters)
    for s in heur:
        assert not validate(inst, s), validate(inst, s)
    summ["heuristic"] = hst
    log(f"heuristic: {hst}")

    exact = []
    if not skip_exact:
        exact, est = pareto_front(inst, time_limit=time_limit, log=log, seeds=heur)
        for s in exact:
            errs = validate(inst, s)
            assert not errs, errs
        summ["exact"] = est
        summ["coverage_exact_over_heur"] = coverage(exact, heur, inst)
        summ["coverage_heur_over_exact"] = coverage(heur, exact, inst)
        log(f"exact: {est}")

    for name, sols in (("exact", exact), ("heuristic", heur)):
        with open(out / f"front_{name}.json", "w", encoding="utf-8") as f:
            json.dump([s.to_dict(inst) for s in sols], f, indent=1)

    ref = exact or heur
    best = max(ref, key=lambda s: (lambda v: (v[0], -v[1], -v[2]))(objective_vector(inst, s)))
    summ["best_profit"] = evaluate(inst, best)
    summ["front_table"] = [list(objective_vector(inst, s)) + [evaluate(inst, s)["n_late"]]
                           for s in ref]

    plot_pareto(inst, exact, heur, out / "pareto.png")
    plot_pareto_interactive(inst, exact, heur, out / "pareto.html")
    plot_gantt(inst, best, out / "gantt_max_profit.png")
    # compromise = point closest to the ideal point (normalised objectives)
    nz = [s for s in ref if objective_vector(inst, s)[0] > 0]
    if nz:
        V = [objective_vector(inst, s) for s in nz]
        lo = [min(v[c] for v in V) for c in range(3)]
        hi = [max(v[c] for v in V) for c in range(3)]
        rng = [max(1, hi[c] - lo[c]) for c in range(3)]

        def dist(v):
            return (((hi[0] - v[0]) / rng[0]) ** 2 + ((v[1] - lo[1]) / rng[1]) ** 2
                    + ((v[2] - lo[2]) / rng[2]) ** 2)
        comp = nz[min(range(len(nz)), key=lambda q: dist(V[q]))]
        summ["compromise"] = evaluate(inst, comp)
        plot_gantt(inst, comp, out / "gantt_compromise.png")
        low = min(nz, key=lambda s: (objective_vector(inst, s)[1], -objective_vector(inst, s)[0]))
        plot_gantt(inst, low, out / "gantt_min_multitasking.png")
    with open(out / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summ, f, indent=1)
    log_f.close()
    return summ


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--instances", nargs="*", default=["toy", "medium"])
    p.add_argument("--time-limit", type=float, default=120)
    p.add_argument("--heur-iters", type=int, default=10)
    p.add_argument("--generated", action="store_true")
    p.add_argument("--heuristic-only", action="store_true")
    p.add_argument("--exact-max-jobs", type=int, default=20,
                   help="generated instances with more jobs run the heuristic only")
    p.add_argument("--resume", action="store_true",
                   help="reuse results/generated/<name>/summary.json when present")
    a = p.parse_args()

    if a.generated:
        gen_dir = ROOT / "Datasets-generated"
        gen_dir.mkdir(exist_ok=True)
        configs = [  # (staff, jobs, horizon, quals, load, seed)
            (3, 6, 8, 4, 1.3, 1),
            (4, 10, 12, 5, 1.3, 2),
            (5, 12, 15, 6, 1.3, 3),
            (5, 15, 20, 8, 1.5, 4),
            (6, 20, 25, 8, 1.5, 5),
            (8, 30, 30, 10, 1.5, 6),
        ]
        rows = []
        for (ns, nj, h, nq, ld, sd) in configs:
            data = generate(ns, nj, h, nq, ld, seed=sd)
            name = f"gen_s{ns}_j{nj}_h{h}"
            with open(gen_dir / f"{name}.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            inst = instance_from_dict(data, name)
            out = ROOT / "results" / "generated" / name
            if a.resume and (out / "summary.json").exists():
                rows.append(json.loads((out / "summary.json").read_text()))
                continue
            s = run(inst, out, a.time_limit, a.heur_iters,
                    skip_exact=a.heuristic_only or nj > a.exact_max_jobs)
            rows.append(s)
        with open(ROOT / "results" / "generated" / "benchmark.json", "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=1)
        return

    for name in a.instances:
        inst = load_instance(ROOT / "Datasets-20261106" / f"{name}_instance.json")
        run(inst, ROOT / "results" / name, a.time_limit, a.heur_iters, skip_exact=a.heuristic_only)


if __name__ == "__main__":
    main()
