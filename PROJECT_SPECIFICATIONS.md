# Decision Modelling Project: Staffing Collaborators on Projects

**Course:** MSCAI002 – Decision Modeling (MSc AI, Paris-Saclay, 2026–2027)  
**Instructor:** Vincent Mousseau  
**Client / Context:** CompuOpti (CEO: Margaux Dourtille)

---

## 1. Context & Problem Overview

CompuOpti designs and implements optimization and decision-support solutions for clients. The company employs software engineers who must be allocated to client projects.
- Each project requires a specific number of **person-days** across different skill sets (e.g., optimization, project management, web development).
- The planning takes place over a discrete **time horizon** considering working days.
- Not all projects can necessarily be staffed due to resource limits; uncompleted projects generate no revenue.
- Each staff member possesses a subset of qualifications and has pre-scheduled **leave days** (vacations).
- Each completed project yields a financial **gain** (revenue), but projects completed after their **due date** incur a **daily financial penalty**.
- The main goal is to determine optimal staff assignments and project schedules to maximize net profit (and explore multi-objective trade-offs).

---

## 2. Mathematical Model Formulation

*(Directly derived from the course slides / screenshots)*

### 2.1 Parameters & Sets (Notations)

- $\mathcal{H} = \{1, \dots, h\}$ : Discrete time horizon ($h \in \mathbb{N} \setminus \{0\}$).
- $\mathcal{Q} = \{1, \dots, q\}$ : Set of all qualifications (skills).
- $\mathcal{S} = \{1, \dots, n\}$ : Set of staff members (collaborators).
- For each staff member $i \in \mathcal{S}$:
  - $\mathcal{Q}_i^S \subseteq \mathcal{Q}$ : Set of qualifications mastered by person $i$.
  - $\mathcal{V}_i^S \subseteq \mathcal{H}$ : Set of scheduled vacation / leave days for person $i$.
- $\mathcal{J} = \{1, \dots, m\}$ : Set of candidate projects (jobs).
- For each project $j \in \mathcal{J}$:
  - $\mathcal{Q}_j^J \subseteq \mathcal{Q}$ : Set of qualifications required by project $j$.
  - $n_{j,k} \in \mathbb{N}$ : Number of person-days required for skill $k \in \mathcal{Q}_j^J$.
  - $g_j \in \mathbb{N}$ : Financial gain / revenue earned if project $j$ is completed.
  - $d_j \in \mathcal{H}$ : Due date (deadline) for project $j$.
  - $c_j \in \mathbb{N}$ : Financial penalty per day of delay (tardiness) for project $j$.

---

### 2.2 Decision Variables

- $X_{i,j,k,t} \in \{0, 1\}$ : Binary variable equal to $1$ if person $i$ works on qualification $k$ for project $j$ on day $t$, and $0$ otherwise ($\forall i \in \mathcal{S}, j \in \mathcal{J}, k \in \mathcal{Q}, t \in \mathcal{H}$).
- $Y_j \in \{0, 1\}$ : Binary variable equal to $1$ if project $j$ is fully completed, and $0$ otherwise ($\forall j \in \mathcal{J}$).
- $E_j \in \mathcal{H}$ : Completion date (end date / completion day) of project $j$ ($\forall j \in \mathcal{J}$).
- $L_j \in \mathbb{N}$ : Number of days of delay / lateness for project $j$ ($\forall j \in \mathcal{J}$).

---

### 2.3 Objective Function

Maximize total profit (revenue from completed projects minus delay penalties):

$$\max \sum_{j \in \mathcal{J}} \left( Y_j \times g_j - L_j \times c_j \right)$$

---

### 2.4 Constraints

1. **Daily Staff Assignment Uniqueness Constraint:**
   A staff member can work on at most one project and one qualification per day.
   $$\sum_{j \in \mathcal{J}} \sum_{k \in \mathcal{Q}} X_{i,j,k,t} \le 1 \quad \forall i \in \mathcal{S}, \forall t \in \mathcal{H}$$

2. **Leave / Vacation Constraint:**
   A staff member cannot be assigned to any project on their leave days.
   $$\sum_{j \in \mathcal{J}} \sum_{k \in \mathcal{Q}} X_{i,j,k,t} = 0 \quad \forall i \in \mathcal{S}, \forall t \in \mathcal{V}_i^S$$

3. **Staff & Project Qualification Eligibility:**
   An assignment is valid only if person $i$ holds skill $k$ AND project $j$ requires skill $k$.
   $$X_{i,j,k,t} = 0 \quad \forall i \in \mathcal{S}, \forall j \in \mathcal{J}, \forall k \in \mathcal{Q} \text{ such that } (k \notin \mathcal{Q}_i^S \lor k \notin \mathcal{Q}_j^J), \forall t \in \mathcal{H}$$

4. **Project Qualification Coverage (Lower Bound):**
   If project $j$ is completed ($Y_j = 1$), all required person-days $n_{j,k}$ for each skill $k \in \mathcal{Q}_j^J$ must be fulfilled.
   $$Y_j \times n_{j,k} \le \sum_{i \in \mathcal{S}} \sum_{t \in \mathcal{H}} X_{i,j,k,t} \quad \forall j \in \mathcal{J}, \forall k \in \mathcal{Q}_j^J$$

5. **Maximum Workdays Cap per Qualification (Upper Bound):**
   Prevents redundant assignments beyond what is needed for skill $k$ in project $j$.
   $$\sum_{i \in \mathcal{S}} \sum_{t \in \mathcal{H}} X_{i,j,k,t} \le n_{j,k} \quad \forall j \in \mathcal{J}, \forall k \in \mathcal{Q}_j^J$$
   *(Note: Constraints 4 & 5 ensure that when $Y_j = 1$, exactly $n_{j,k}$ days are delivered).*

6. **Completion Date Determination:**
   The completion date $E_j$ must be at least the latest day on which work was performed on project $j$.
   $$X_{i,j,k,t} \times t \le E_j \quad \forall i \in \mathcal{S}, \forall j \in \mathcal{J}, \forall k \in \mathcal{Q}, \forall t \in \mathcal{H}$$

7. **Lateness / Delay Calculation:**
   Lateness is defined as the excess of the completion date over the due date $d_j$ ($L_j \ge \max(0, E_j - d_j)$).
   $$E_j - d_j \le L_j \quad \forall j \in \mathcal{J}$$
   *(With $L_j \in \mathbb{N}$, $L_j \ge 0$, and minimization of $-L_j \times c_j$).*

8. **Variable Domains:**
   $$X_{i,j,k,t} \in \{0, 1\} \quad \forall i \in \mathcal{S}, \forall j \in \mathcal{J}, \forall k \in \mathcal{Q}, \forall t \in \mathcal{H}$$
   $$Y_j \in \{0, 1\} \quad \forall j \in \mathcal{J}$$
   $$E_j \in \mathcal{H} \quad \forall j \in \mathcal{J}$$
   $$L_j \in \mathbb{N} \quad \forall j \in \mathcal{J}$$

---

## 3. Multi-Objective Criteria & Extensions (from Project PDF)

The project aims to calculate the **set of non-dominated (Pareto-optimal) solutions** for a multi-objective formulation. Other relevant objectives to explore include:
1. **Maximize total profit realized** (base model).
2. **Minimize actual project execution time / makespan:** $\min \max_{j} E_j$ or $\min \sum_{j} E_j$.
3. **Minimize multitasking / project switching:** Minimize the number of distinct projects assigned to each employee.
4. **Minimize number of late projects:** $\min \sum_{j} \mathbb{I}(L_j > 0)$.
5. **Visualization requirement:**
   - Visualizing the Pareto front (non-dominated solutions) in **objective space**.
   - Visualizing specific schedules (Gantt charts / allocations) in **decision space**.

---

## 4. Dataset Structure & JSON Mapping

The workspace contains instance datasets under `Datasets-20261106/`:
- `toy_instance.json`
- `medium_instance.json`
- `large_instance.json`

### JSON Schema Mapping

| JSON Key | Mathematical Symbol | Description |
| :--- | :--- | :--- |
| `horizon` | $h$ | Planning horizon length ($\mathcal{H} = \{1, \dots, h\}$) |
| `qualifications` | $\mathcal{Q}$ | List of qualification identifiers, e.g., `["A", "B", "C"]` |
| `staff` | $\mathcal{S}$ | List of collaborators |
| `staff[i].name` | - | Collaborator identifier / name |
| `staff[i].qualifications` | $\mathcal{Q}_i^S$ | Subset of qualifications possessed by staff $i$ |
| `staff[i].vacations` | $\mathcal{V}_i^S$ | Days on leave (1-indexed integers) |
| `jobs` | $\mathcal{J}$ | List of candidate projects |
| `jobs[j].name` | - | Project identifier |
| `jobs[j].gain` | $g_j$ | Revenue for completing project $j$ |
| `jobs[j].due_date` | $d_j$ | Target completion day |
| `jobs[j].daily_penalty` | $c_j$ | Cost penalty per day of delay |
| `jobs[j].working_days_per_qualification` | $\{k: n_{j,k}\}$ | Dict mapping qualification $k$ to required person-days $n_{j,k}$ |

*(Note: In addition to the provided instances, you are required to implement an **instance generator**).*

---

## 5. Recommended Solvers & Frameworks

Multiple solvers and modeling libraries are available for this MILP / multi-objective problem:

| Tool / Solver | Description & Links |
| :--- | :--- |
| **Gurobi** | Commercial high-performance MILP solver (free academic license).<br>• [Official Site](https://www.gurobi.com/)<br>• [Guide Installation Gurobi](https://centralesupelec.edunao.com/pluginfile.php/612225/mod_page/content/1/Guide_Installation_de_Gurobi.pdf)<br>• [TP0.ipynb](https://centralesupelec.edunao.com/pluginfile.php/612225/mod_page/content/1/TP0-Corrig%C3%A9.ipynb) |
| **IBM CPLEX / OPL** | Industrial MILP and CP solver (free academic initiative).<br>• [CPLEX Optimizer](https://www.ibm.com/fr-fr/analytics/cplex-optimizer) |
| **Google OR-Tools** | Open-source suite for combinatorial optimization (Linear/Integer Programming & CP-SAT).<br>• [Google OR-Tools](https://developers.google.com/optimization?hl=en) |
| **Pyomo** | Flexible, solver-agnostic Python modeling framework supporting Gurobi, CPLEX, CBC, GLPK, etc.<br>• [Pyomo](http://www.pyomo.org/) |
| **COIN-OR** | Open-source operations research initiative (CBC, Clp, PuLP).<br>• [COIN-OR](http://www.coin-or.org/) |

---

## 6. Deliverables & Project Workflow

1. **Team:** Groups of 3 students.
2. **Implementation:**
   - Mathematical formulation (MILP / CP).
   - Heuristics / Metaheuristics (e.g., NSGA-II, local search) if exact methods scale poorly on large instances.
   - Instance generator.
   - Pareto front computation & visualization.
3. **Submission & Defense:**
   - Updated Git repository with well-documented code.
   - Presentation slides detailing the models, experimental comparisons across datasets, and visualizations.
