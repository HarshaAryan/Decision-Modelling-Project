"""Sanity tests:  python -m pytest tests -q"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from data_loader import instance_from_dict, load_instance  # noqa: E402
from exact_solver import pareto_front, solve  # noqa: E402
from heuristic_solver import heuristic_front  # noqa: E402
from instance_generator import generate  # noqa: E402
from solution import Solution, dominates, evaluate, objective_vector, validate  # noqa: E402

TOY = ROOT / "Datasets-20261106" / "toy_instance.json"


def test_toy_optimal_profit_is_65():
    inst = load_instance(TOY)
    sol = solve(inst, time_limit=30)
    assert sol.meta["status"] == "optimal"
    assert not validate(inst, sol)
    assert evaluate(inst, sol)["profit"] == 65


def test_toy_front_is_exact_and_non_dominated():
    inst = load_instance(TOY)
    front, st = pareto_front(inst, time_limit=30, log=lambda *_: None)
    assert st["exact"]
    vecs = [objective_vector(inst, s) for s in front]
    assert (65, 2, 3) in vecs and (65, 3, 2) in vecs
    assert not any(dominates(a, b) for a in vecs for b in vecs)


def test_heuristic_solutions_are_feasible():
    inst = load_instance(TOY)
    front, _ = heuristic_front(inst, n_iter=3)
    assert front and all(not validate(inst, s) for s in front)


def test_validator_catches_violations():
    inst = load_instance(TOY)
    # Liam (index 1) is on vacation on day 1; Emma (2) has no qualification A
    bad = Solution([(1, 0, "A", 1), (2, 0, "A", 3), (0, 0, "A", 2), (0, 1, "B", 2)])
    errs = validate(inst, bad)
    assert any("vacation" in e for e in errs)
    assert any("lacks qualification" in e for e in errs)
    assert any("assignments on day" in e for e in errs)


def test_generator_roundtrip():
    data = generate(4, 8, 10, 5, seed=7)
    inst = instance_from_dict(data, "gen")
    sol = solve(inst, time_limit=20)
    assert not validate(inst, sol)
