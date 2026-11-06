# Decision Modelling Project: Staffing Collaborators on Projects (CompuOpti)

**Course:** MSCAI002 – Decision Modeling (MSc Artificial Intelligence, Paris-Saclay, 2026–2027)  
**Instructor:** Vincent Mousseau  
**Client / Case Study:** CompuOpti (CEO: Margaux Dourtille)

---

## 1. Project Overview & Context

CompuOpti designs and deploys optimization and decision-support algorithms for enterprise clients. The firm employs software engineers who must be allocated to client projects over a discrete planning horizon of working days.

### Key Constraints & Business Rules
1. **Qualification Matching:** An employee can only be assigned to a project task if they possess the required qualification.
2. **Daily Assignment Uniqueness:** At any given day, an employee can work on at most one project and one qualification.
3. **Leave Days:** Employees cannot be assigned on scheduled leave/vacation days.
4. **Qualification Coverage:** A project is marked completed if and only if all required person-days for all its required qualifications are fully staffed.
5. **Single Execution:** A project can be executed at most once within the horizon.
6. **Due Dates & Penalties:** Projects have a due date. If finished after the due date, a financial penalty is deducted for each day of delay.
7. **Profit Realization:** Projects generate a fixed financial gain only when completed.

---

## 2. Mathematical Formulation

### 2.1 Notations & Parameters
- $\mathcal{H} = \{1, \dots, h\}$: Planning horizon ($h \in \mathbb{N} \setminus \{0\}$).
- $\mathcal{Q} = \{1, \dots, q\}$: Set of qualifications (skills).
- $\mathcal{S} = \{1, \dots, n\}$: Set of staff members.
  - $\mathcal{Q}_i^S \subseteq \mathcal{Q}$: Qualifications mastered by employee $i \in \mathcal{S}$.
  - $\mathcal{V}_i^S \subseteq \mathcal{H}$: Vacation days of employee $i \in \mathcal{S}$.
- $\mathcal{J} = \{1, \dots, m\}$: Set of candidate projects.
  - $\mathcal{Q}_j^J \subseteq \mathcal{Q}$: Qualifications required by project $j \in \mathcal{J}$.
  - $n_{j,k} \in \mathbb{N}$: Required person-days for skill $k \in \mathcal{Q}_j^J$.
  - $g_j \in \mathbb{N}$: Gain / revenue earned upon completing project $j$.
  - $d_j \in \mathcal{H}$: Due date for project $j$.
  - $c_j \in \mathbb{N}$: Daily penalty cost for delay on project $j$.

### 2.2 Decision Variables
- $X_{i,j,k,t} \in \{0, 1\}$: $1$ if person $i$ works on skill $k$ for project $j$ on day $t$; $0$ otherwise ($\forall i \in \mathcal{S}, j \in \mathcal{J}, k \in \mathcal{Q}, t \in \mathcal{H}$).
- $Y_j \in \{0, 1\}$: $1$ if project $j$ is completed; $0$ otherwise ($\forall j \in \mathcal{J}$).
- $E_j \in \mathcal{H}$: Completion date of project $j$ ($\forall j \in \mathcal{J}$).
- $L_j \in \mathbb{N}$: Delay / tardiness days for project $j$ ($\forall j \in \mathcal{J}$).

### 2.3 Objective Function
Maximize net profit:
$$\max \sum_{j \in \mathcal{J}} \left( Y_j \times g_j - L_j \times c_j \right)$$

### 2.4 Model Constraints
1. **Daily staff uniqueness:**
   $$\sum_{j \in \mathcal{J}} \sum_{k \in \mathcal{Q}} X_{i,j,k,t} \le 1 \quad \forall i \in \mathcal{S}, \forall t \in \mathcal{H}$$

2. **Leave days:**
   $$\sum_{j \in \mathcal{J}} \sum_{k \in \mathcal{Q}} X_{i,j,k,t} = 0 \quad \forall i \in \mathcal{S}, \forall t \in \mathcal{V}_i^S$$

3. **Ineligible skill assignments:**
   $$X_{i,j,k,t} = 0 \quad \forall i \in \mathcal{S}, \forall j \in \mathcal{J}, \forall k \in \mathcal{Q} \text{ such that } (k \notin \mathcal{Q}_i^S \lor k \notin \mathcal{Q}_j^J), \forall t \in \mathcal{H}$$

4. **Qualification requirement lower bound:**
   $$Y_j \times n_{j,k} \le \sum_{i \in \mathcal{S}} \sum_{t \in \mathcal{H}} X_{i,j,k,t} \quad \forall j \in \mathcal{J}, \forall k \in \mathcal{Q}_j^J$$

5. **Workload upper bound:**
   $$\sum_{i \in \mathcal{S}} \sum_{t \in \mathcal{H}} X_{i,j,k,t} \le n_{j,k} \quad \forall j \in \mathcal{J}, \forall k \in \mathcal{Q}_j^J$$

6. **Completion date bound:**
   $$X_{i,j,k,t} \times t \le E_j \quad \forall i \in \mathcal{S}, \forall j \in \mathcal{J}, \forall k \in \mathcal{Q}, \forall t \in \mathcal{H}$$

7. **Lateness bound:**
   $$E_j - d_j \le L_j \quad \forall j \in \mathcal{J}, \quad L_j \ge 0$$

---

## 3. Multi-Objective Extensions

The project requires finding and visualizing **non-dominated (Pareto-optimal) solutions** across competing objectives:
1. **$f_1$ (Profit):** Maximize net financial gain: $\sum_j (Y_j g_j - L_j c_j)$.
2. **$f_2$ (Makespan / Project Time):** Minimize latest completion time: $\min \max_j E_j$ or $\min \sum_j E_j$.
3. **$f_3$ (Employee Workload / Multitasking):** Minimize distinct projects per collaborator.
4. **$f_4$ (Lateness Count):** Minimize total late projects: $\min \sum_j \mathbb{I}(L_j > 0)$.

---

## 4. Repository Structure & Dataset Format

```text
.
├── Datasets-20261106/
│   ├── toy_instance.json
│   ├── medium_instance.json
│   └── large_instance.json
├── PROJECT_SPECIFICATIONS.md
├── README.md
├── plan.md
└── src/ (to be created)
    ├── data_loader.py
    ├── instance_generator.py
    ├── exact_solver.py
    ├── heuristic_solver.py
    └── visualization.py
```

### JSON Schema
Each JSON file contains:
- `horizon` (int): Total days in the time horizon.
- `qualifications` (list of str): List of qualification names, e.g., `["A", "B", "C"]`.
- `staff` (list of dicts): Staff members with `name`, `qualifications` (list of str), and `vacations` (list of ints, 1-indexed).
- `jobs` (list of dicts): Projects with `name`, `gain`, `due_date`, `daily_penalty`, and `working_days_per_qualification` (dict mapping qualification name to person-days).

---

## 5. Supported Solvers & Frameworks

| Tool | Focus | Documentation / Links |
| :--- | :--- | :--- |
| **Gurobi** | State-of-the-art commercial MILP solver | [gurobi.com](https://www.gurobi.com/) |
| **IBM CPLEX / OPL** | High-performance industrial MILP & CP solver | [cplex-optimizer](https://www.ibm.com/fr-fr/analytics/cplex-optimizer) |
| **Google OR-Tools** | Versatile open-source LP, MIP & CP-SAT solver | [developers.google.com/optimization](https://developers.google.com/optimization?hl=en) |
| **Pyomo** | Solver-agnostic Python algebraic modeling interface | [pyomo.org](http://www.pyomo.org/) |
| **COIN-OR / PuLP** | Open-source operations research libraries | [coin-or.org](http://www.coin-or.org/) |

---

## 6. How to Run & Requirements

Recommended environment: Python 3.10+ with:
```bash
pip install gurobipy ortools pyomo matplotlib seaborn pandas numpy
```

Run test instance verification:
```bash
python3 -c "import json; data=json.load(open('Datasets-20261106/toy_instance.json')); print('Loaded horizon:', data['horizon'])"
```
