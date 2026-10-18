# 🌊 LeakLens — Semester 1 Comprehensive Technical Documentation

> **Note:** this document describes the original two-scenario prototype (Algorithms 1-3 below). The final Semester 1 system, scenarios and results are in `SEMESTER_1_COMPLETION.md`; the run instructions are in `README.md`.
**Project Title:** Intelligent Water Network Leak Detection and Localization  
**Course:** B.Tech Project (BTP) — Semester 1 Final Deliverable  
**Institution:** Indian Institute of Information Technology (IIIT) Kottayam  
**Supervised By:** Dr. Divya Sindhu Lekha  
**Date:** October 2026  

---

## 📑 Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [End-to-End System Architecture](#2-end-to-end-system-architecture)
3. [Physical Hydraulic Modeling & Benchmark Network](#3-physical-hydraulic-modeling--benchmark-network)
4. [Governing Hydraulic Equations](#4-governing-hydraulic-equations)
5. [Complete Algorithmic Formulations](#5-complete-algorithmic-formulations)
   - [Algorithm 1: Time-Synchronized Anomaly Detection](#algorithm-1-time-synchronized-pressure-residual-anomaly-detection)
   - [Algorithm 2: Directional Mass Imbalance / Flow Divergence](#algorithm-2-directional-mass-imbalance--flow-divergence-kirchhoffs-law)
   - [Algorithm 3: Composite Localization & Top-K Ranking](#algorithm-3-composite-hydraulic-localization--top-k-ranking)
6. [Datasets & Experimental Scenarios](#6-datasets--experimental-scenarios)
7. [Experimental Results & Verification](#7-experimental-results--verification)
8. [Backend API Architecture (FastAPI)](#8-backend-api-architecture-fastapi)
9. [Frontend Dashboard Architecture (Next.js & React Flow)](#9-frontend-dashboard-architecture-nextjs--react-flow)
10. [How to Run the Entire Application](#10-how-to-run-the-entire-application)
11. [Semester 2 Research Roadmap](#11-semester-2-research-roadmap)

---

## 1. Executive Summary

Water Distribution Networks (WDNs) lose substantial treated drinking water—often 30% to 40% in municipal systems—due to hidden pipe bursts and background leakage (Non-Revenue Water). Traditional field search methods (such as acoustic listening sticks) are labor-intensive, slow, and cannot monitor underground pipelines in real time.

For **Semester 1**, we have built **LeakLens**, a complete software prototype that combines:
1. **Hydraulic Simulation:** EPANET / WNTR extended-period simulation on the 97-node benchmark network.
2. **Dual-Signal Machine Learning & Physics-Informed Analytics:** Uses **both pressure head residuals and pipe flow divergence** based on physical mass conservation.
3. **Interactive Web Dashboard:** A Next.js + React Flow + FastAPI platform displaying live network topology, real-time node inspection cards, 24-hour pressure time-series graphs, and Top-$K$ candidate leak localization.

The first version of the system reached 100% Top-1 on two large-leak scenarios. That was a small test. The extended evaluation (about 590 scenarios on three networks) is in `SEMESTER_1_COMPLETION.md`; use those numbers, not the 100% figure.

---

## 2. End-to-End System Architecture

The project is structured as a modular monorepo:

```
water+leak/
│
├── data/
│   ├── networks/
│   │   └── Net3.inp                     # Benchmark network topology (EPANET format)
│   └── raw_simulations/
│       ├── baseline_pressures.csv       # 24-hour clean normal pressures
│       ├── baseline_flows.csv           # 24-hour clean normal pipe flows
│       ├── leak_15_pressures.csv        # Outer branch leak pressures
│       ├── leak_15_flows.csv            # Outer branch leak flows
│       ├── leak_115_pressures.csv       # Central 4-way intersection leak pressures
│       └── leak_115_flows.csv           # Central 4-way intersection leak flows
│
├── simulation/
│   ├── download_networks.py             # Automates downloading standard benchmark models
│   ├── simulator.py                     # WNTR wrapper configuring 24h PDD simulation
│   └── generate_dataset.py              # Script generating baseline and leak scenario datasets
│
├── ml_pipeline/
│   ├── detector.py                      # Stage 1: Time-synchronized residual anomaly detector
│   ├── localizer.py                     # Stage 2: Directional mass divergence + pressure localizer
│   └── evaluate.py                      # Validation script calculating Top-1 and Top-K accuracy
│
├── backend/
│   ├── main.py                          # FastAPI application entry point with CORS
│   ├── schemas.py                       # Pydantic schemas (NodeMetric, FlowMetric, AnalysisResponse)
│   ├── database.py & models.py          # Relational metadata persistence
│   └── routers/
│       ├── network_api.py               # GET /api/network (Serves graph topology JSON)
│       └── analysis_api.py              # GET /api/analyze/{scenario} (Executes inference)
│
└── frontend/
    ├── src/app/
    │   ├── page.tsx                     # Main dashboard layout and scenario selection
    │   └── globals.css                  # Tailwind styles
    └── src/components/
        └── NetworkMap.tsx               # Interactive React Flow map, custom nodes, 
                                         # 24-hr Recharts graphs, and telemetry panel
```

```
[Simulation Layer (WNTR/EPANET)]
           │
           ▼ (24-Hour Pressures & Flows CSVs)
[ML Pipeline Layer (detector.py + localizer.py)]
           │
           ▼ (Top-K Predictions & Telemetry Metrics)
[Backend Layer (FastAPI REST Endpoints)]
           │
           ▼ (JSON API over HTTP)
[Frontend Layer (Next.js Dashboard + React Flow Canvas + Recharts)]
```

---

## 3. Physical Hydraulic Modeling & Benchmark Network

The system models the benchmark **EPANET Net3** network, an internationally recognized municipal water distribution benchmark.

### Network Composition:
* **92 Junction Nodes ($\mathcal{V}_{\text{junc}}$):** Consumer demand draw points where water pressure is measured.
* **2 Reservoirs ($\mathcal{V}_{\text{res}}$):** Infinite water sources (Lake and River) providing constant hydraulic head boundary conditions.
* **3 Tanks ($\mathcal{V}_{\text{tank}}$):** Elevated storage tanks (Tanks 1, 2, 3) with dynamic water levels that store and release water.
* **117 Pipes ($\mathcal{E}_{\text{pipe}}$):** Closed conduits carrying pressurized water.
* **2 Pumps ($\mathcal{E}_{\text{pump}}$):** Mechanical pump stations adding energy head to the water stream.
* **Total Nodes:** 97 nodes; **Total Links:** 119 links.

### Pressure-Dependent Demand (PDD) vs Demand-Driven Analysis (DDA):
Standard EPANET uses Demand-Driven Analysis (DDA), which assumes consumer demand is delivered regardless of pipe pressure. This fails during leaks because water loss depends directly on pressure.  
We use `wntr.sim.WNTRSimulator` running **Pressure-Dependent Demand (PDD)**, ensuring that leak flow rate naturally responds to pressure variations in the surrounding pipes.

---

## 4. Governing Hydraulic Equations

### 4.1. Diurnal Consumer Demand Pattern
Water consumption varies dramatically over a 24-hour cycle (morning and evening peaks, nighttime lull). At junction $i$ and time $t$:
$$D_i(t) = D_{\text{base}, i} \times M(t)$$
* $D_{\text{base}, i}$: Nominal base consumption.
* $M(t)$: Dimensionless hourly demand multiplier.

### 4.2. Pipe Friction Head Loss (Darcy-Weisbach / Hazen-Williams)
As water moves through a pipe of length $L$ and diameter $d$ at velocity $v$, frictional head loss $h_f$ is:
$$h_f = f \cdot \frac{L}{d} \cdot \frac{v^2}{2g} \propto Q^2$$
* **Physical implication:** When morning demand spikes, flow velocity $v$ increases $\implies$ friction head loss $h_f$ increases $\implies$ junction pressure drops naturally. A naïve static threshold would trigger false alarms every morning.

### 4.3. Physical Orifice Leak Equation (Torricelli's Law)
When a physical pipe crack of area $A_{\text{leak}}$ opens at junction $i^*$, water discharges into the atmosphere according to:
$$Q_{\text{leak}, i^*}(t) = C_d \, A_{\text{leak}} \sqrt{2 g P_{i^*}(t)} \quad \text{for } t \ge t_{\text{start}}$$
* $C_d = 0.75$: Discharge coefficient.
* $A_{\text{leak}}$: Orifice area ($0.05\,\text{m}^2$ in Scenario 1; $0.03\,\text{m}^2$ in Scenario 2).
* $g = 9.81\,\text{m/s}^2$: Gravitational acceleration.
* $P_{i^*}(t)$: Gauge pressure head at the leaking junction.

---

## 5. Complete Algorithmic Formulations

Our detection and localization engine operates in three sequential mathematical stages:

```
[Hourly Observed Matrices: P(t) and Q(t)]
                   │
                   ▼
  Stage 1: Time-Synchronized Residuals ──► Has Anomaly? (Yes/No)
                   │ (If Yes)
                   ▼
  Stage 2: Directional Mass Imbalance ──► Localizes True Flow Sink
                   │
                   ▼
  Stage 3: Composite Scoring Engine   ──► Outputs Top-1 & Top-K Candidates
```

---

### Algorithm 1: Time-Synchronized Pressure Residual Anomaly Detection

**Source File:** `ml_pipeline/detector.py`

#### Purpose:
Determines whether an abnormal leak event has occurred in the network without triggering false alarms from routine daily usage variations.

#### Formulation:
For every junction $i \in \mathcal{V}$ and every hourly timestep $t \in \{0, 1, \dots, 24\}$:
$$\Delta P_i(t) = P_{\text{baseline}, i}(t) - P_{\text{observed}, i}(t)$$

* **Why Synchronized:** Subtracting the baseline at the **exact matching hour $t$** cancels out the diurnal demand cycle:
  $$\Delta P_i(t) = \left[ P_{\text{clean}}(t) \right] - \left[ P_{\text{clean}}(t) - \Delta P_{\text{leak}}(t) \right] = \Delta P_{\text{leak}}(t)$$

#### Decision Rule:
$$\text{Anomaly Flag} = \begin{cases} 
\text{True} & \text{if } \displaystyle\max_{i \in \mathcal{V}, \, t} \Delta P_i(t) > \tau_P \\ 
\text{False} & \text{otherwise} 
\end{cases}$$
* Threshold $\tau_P = 0.5\,\text{meters}$. If any node exhibits a drop exceeding $0.5\,\text{m}$, the system flags an active leak.

---

### Algorithm 2: Directional Mass Imbalance / Flow Divergence (Kirchhoff's Law)

**Source File:** `ml_pipeline/localizer.py`

#### Purpose:
Eliminates false candidate rankings at reservoir pumps and distinguishes pure leak sinks from transmission pipes.

#### Mathematical Foundation:
In graph topology $\mathcal{G} = (\mathcal{V}, \mathcal{E})$, each pipe link $p$ has an oriented start node and end node. We define the directional sign of link $p$ relative to node $i$ as:
$$\operatorname{sign}(p, i) = \begin{cases} 
+1.0 & \text{if pipe } p \text{ terminates at node } i \quad (\text{Inflow into node } i) \\ 
-1.0 & \text{if pipe } p \text{ originates at node } i \quad (\text{Outflow from node } i) 
\end{cases}$$

For any node $i$, the net mass divergence residual at timestep $t$ is:
$$\Delta Q_{\text{div}, i}(t) = \sum_{p \in \mathcal{E}(i)} \operatorname{sign}(p, i) \times \left( Q_{\text{observed}, p}(t) - Q_{\text{baseline}, p}(t) \right)$$

Taking the peak divergence over time:
$$\Delta Q_{\text{div}, i} = \max_{t} \Delta Q_{\text{div}, i}(t)$$

#### Physical Behavior:
* **Normal Junctions:** Flow in = Flow out $\implies \Delta Q_{\text{div}, i} \approx 0.0\,\text{m}^3/\text{s}$.
* **Supply Pumps / Reservoirs:** Inflow surge equals outflow surge $\implies \Delta Q_{\text{div}, \text{pump}} \approx 0.0\,\text{m}^3/\text{s}$ (water passes straight through).
* **True Leak Node $i^*$:** Water enters through upstream pipes but does not leave through downstream pipes $\implies \mathbf{\Delta Q_{\text{div}, i^*} = +Q_{\text{leak}} > 0}$ (net mass loss).

---

### Algorithm 3: Composite Hydraulic Localization & Top-$K$ Ranking

**Source Files:** `ml_pipeline/localizer.py`, `backend/routers/analysis_api.py`

#### Purpose:
Computes a final composite score for all candidate junctions to rank the most probable leak location (Top-1) and identify the surrounding candidate cluster (Top-$K$).

#### Formulation:
For each candidate junction $i \in \mathcal{V}_{\text{junc}}$:
$$\mathcal{S}(i) = \underbrace{\max_{t} \Delta P_i(t)}_{\text{Peak Pressure Head Drop (m)}} + \; \lambda \times \underbrace{\max\left(0, \, \Delta Q_{\text{div}, i}\right)}_{\text{Mass Imbalance Loss (m}^3\text{/s)}}$$

* $\lambda = 50.0$: Dimensional hydraulic scaling coefficient converting volumetric flow loss ($\text{m}^3/\text{s}$) into equivalent pressure head units ($\text{m}$).
* **Candidate Filtering:** Tanks and reservoirs are boundary elements; therefore, candidate ranking is strictly evaluated over consumer junctions $i \in \mathcal{V}_{\text{junc}}$.

#### Ranking Output:
All nodes are sorted in descending order of $\mathcal{S}(i)$:
$$\text{Ranked List} = \operatorname{SortDescending}\Big(\{ \mathcal{S}(i) \mid i \in \mathcal{V}_{\text{junc}} \}\Big)$$
* **Rank #1:** Primary predicted leak location.
* **Ranks #2 through #5:** Top-5 candidate cluster (neighboring physical pipe zone).

---

## 6. Datasets & Experimental Scenarios

All simulation runs model extended-period operations over **24 hours** ($T = 25$ hourly timesteps from $t=0$ to $t=86,400\,\text{s}$).

| Scenario Name | Description | Leak Junction | Leak Area ($A_{\text{leak}}$) | Start Time | Type of Location |
|---|---|:---:|:---:|:---:|---|
| **`baseline`** | Normal Operations | None | $0.0\,\text{m}^2$ | --- | Clean reference baseline |
| **`leak_15`** | Outer Boundary Leak | **Node 15** | $0.05\,\text{m}^2$ | Hour 12 ($43,200\,\text{s}$) | Residential branch dead-end |
| **`leak_115`** | Central Hub Leak | **Node 115** | $0.03\,\text{m}^2$ | Hour 12 ($43,200\,\text{s}$) | Central 4-way loop intersection |

### Generated CSV File Structure:
* `baseline_pressures.csv` ($25 \times 97$ matrix)
* `baseline_flows.csv` ($25 \times 119$ matrix)
* `leak_15_pressures.csv` and `leak_15_flows.csv`
* `leak_115_pressures.csv` and `leak_115_flows.csv`

---

## 7. Experimental Results & Verification

Automated evaluation is executed via `ml_pipeline/evaluate.py`:

```
============================================================
SCENARIO 1: LEAK AT NODE 15 (Outer Branch Tip)
============================================================
True Leak Node:       15
Top 5 Predicted:      ['15', '143', '141', '145', '147']
Top-1 Match:          True  (100% Top-1 Accuracy)
Top-5 Match:          True  (100% Top-5 Accuracy)
Spatial Geometry:     Contiguous linear pipe chain (15 - 143 - 141 - 145 - 147)

============================================================
SCENARIO 2: LEAK AT NODE 115 (Central 4-Way Crossing)
============================================================
True Leak Node:       115
Top 5 Predicted:      ['115', '107', '111', '109', '103']
Top-1 Match:          True  (100% Top-1 Accuracy)
Top-5 Match:          True  (100% Top-5 Accuracy)
Spatial Geometry:     Contiguous radial star cluster around central crossing
============================================================
```

### Performance Summary Table:

| Metric | Scenario 1 (`leak_15`) | Scenario 2 (`leak_115`) | Target Benchmark |
|---|:---:|:---:|:---:|
| **Anomaly Detection Rate** | 100% | 100% | 100% |
| **Top-1 Localization Accuracy** | **100%** | **100%** | $\ge 80\%$ |
| **Top-5 Localization Accuracy** | **100%** | **100%** | $\ge 95\%$ |
| **False Positive Alarm Rate** | 0.0% (Clean baseline = No anomaly) | 0.0% | $\le 5\%$ |
| **Spatial Cluster Contiguity** | 100% connected | 100% connected | Contiguous |

---

## 8. Backend API Architecture (FastAPI)

Built using Python **FastAPI** (`backend/`):

### API Endpoints:

#### 1. `GET /api/network`
Returns network topology coordinates and component classifications.
* **Response:**
  ```json
  {
    "nodes": [
      { "id": "15", "x": 38.68, "y": 23.76, "type": "Junction", "elevation": 0.0 },
      { "id": "River", "x": 23.90, "y": 32.50, "type": "Reservoir", "elevation": 0.0 },
      { "id": "1", "x": 19.50, "y": 20.00, "type": "Tank", "elevation": 71.6 }
    ],
    "edges": [
      { "id": "151", "source": "143", "target": "15" }
    ]
  }
  ```

#### 2. `GET /api/analyze/{scenario_name}`
Triggers detection and composite localization inference.
* **Response Payload:**
  * `has_anomaly` (boolean): Flag indicating leak detection.
  * `predicted_leaks` (list): Top-5 ranked nodes with composite scores.
  * `node_metrics` (dict): For all 97 nodes:
    * `current_pressure`, `baseline_pressure`, `pressure_drop` ($\Delta P$).
    * `flow_divergence` ($\Delta Q_{\text{div}}$ in $\text{m}^3/\text{s}$).
    * `composite_score` ($\mathcal{S}(i)$).
    * `status` ("Predicted Leak Location", "Anomalous Pressure Drop", or "Normal").
    * `baseline_series`: 25 hourly pressure values ($t=0\dots24$).
    * `current_series`: 25 hourly observed pressure values ($t=0\dots24$).
    * `connected_pipes`: List of connected pipe IDs.
  * `flow_metrics` (dict): For all pipes:
    * `current_flow`, `baseline_flow`, `flow_change` ($\Delta Q$).

---

## 9. Frontend Dashboard Architecture (Next.js & React Flow)

Built with **Next.js 14**, **React Flow**, **Tailwind CSS**, and **Recharts** (`frontend/`):

### Core Visual Features:

1. **Topological Coordinate Normalization:**
   Raw EPANET coordinates are dynamically mapped to a 2500px virtual canvas:
   $$\operatorname{posX} = \frac{x - x_{\min}}{x_{\max} - x_{\min}} \cdot 2500, \quad \operatorname{posY} = 2500 - \left( \frac{y - y_{\min}}{y_{\max} - y_{\min}} \cdot 2500 \right)$$
   This prevents node overlap and renders the entire network clearly.

2. **Semantic Visual Node Classification:**
   * 🔵 **Junctions:** Blue circles (`#3b82f6`).
   * 🟢 **Reservoirs (River/Lake):** Emerald green rounded squares (`#10b981`).
   * 🟣 **Tanks (Storage Tanks 1, 2, 3):** Purple rounded boxes (`#8b5cf6`).
   * 🟡 **Anomalous Drop:** Amber warning glow (`#f59e0b`) for nodes with $\Delta P > 3.0\,\text{m}$.
   * 🔴 **Predicted Leak Locations:** Pulsing red circles (`#ef4444`) with outer drop shadow glow.

3. **Node Inspection Card (Floating Panel):**
   * **Dual Telemetry:** Pressure Head vs Baseline + Net Flow Divergence / Mass Imbalance badge.
   * **Score Calculation Breakdown:** Displays $\Delta P + (50 \times \Delta Q_{\text{div}})$.
   * **24-Hour Pressure Line Graph (Recharts):** Interactive hoverable curve comparing baseline (Blue) vs test (Red), highlighting the exact hour the leak occurs.
   * **Connected Pipes Telemetry:** Displays connected pipe IDs, current flow rate ($\text{m}^3/\text{s}$), and flow surge delta ($\Delta Q$).

4. **Interactive Controls:**
   * Node ID Search Bar with auto-zoom.
   * Toggle Node Labels.
   * Toggle Pipe Flow Animations.
   * Fit View button.

---

## 10. How to Run the Entire Application

### Step 1: Activate Virtual Environment and Generate Dataset
```powershell
cd C:\Users\ASUS\Documents\water+leak\simulation
..\venv\Scripts\Activate.ps1
python generate_dataset.py
```

### Step 2: Run Evaluation Benchmark
```powershell
cd C:\Users\ASUS\Documents\water+leak\ml_pipeline
python evaluate.py
```

### Step 3: Start FastAPI Backend Server
Open **PowerShell Terminal 1**:
```powershell
cd C:\Users\ASUS\Documents\water+leak\backend
..\venv\Scripts\Activate.ps1
uvicorn main:app --reload
```
*Backend runs at: `http://localhost:8000` (Swagger docs at `http://localhost:8000/docs`)*

### Step 4: Start Next.js Frontend Dashboard
Open **PowerShell Terminal 2**:
```powershell
cd C:\Users\ASUS\Documents\water+leak\frontend
npm run dev
```
*Frontend runs at: `http://localhost:3000`*

---

## 11. Semester 2 Research Roadmap

Building upon this Semester 1 foundation, the following research objectives are planned for Semester 2:

1. **Realistic Sensor Noise & Missing Data:**
   * Introduce Gaussian sensor noise $\tilde{y}(t) = y(t) + \mathcal{N}(0, \sigma^2)$ ($1\%\text{--}5\%$) to test transducer error tolerance.
   * Simulate sparse sensor instrumentation (monitoring only 20% to 30% of junctions using centrality metrics).
2. **Graph Neural Networks (GNN):**
   * Implement a Spatial-Temporal Graph Convolutional Network (ST-GCN) where graph adjacency $A_{ij}$ is weighted by pipe conductances.
3. **Multi-Leak Simultaneous Detection:**
   * Extend the mass divergence matrix to isolate multiple simultaneous pipe breaks across separate District Metered Areas (DMAs).
4. **Cross-Network Transferability:**
   * Evaluate generalization on other benchmark topologies (e.g., Richmond, CTown, Modena).

---
*End of Semester 1 Documentation.*
