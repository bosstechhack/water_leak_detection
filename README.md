# LeakLens: Water Leak Localization System

BTP Semester 1 deliverable (IIIT Kottayam). Hydraulic simulation (EPANET/WNTR) of three benchmark networks,
a detector that tells a **leak** from demand, pump, reservoir, tank, blockage and ageing changes, a topology-aware
**leak localizer**, a FastAPI backend (SQLite) and a Next.js dashboard.

All results come from simulation, not real sensor data.

## Prerequisites
- Python 3.9+ (tested on 3.14) and Node.js 18+

## Setup
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r backend/requirements.txt      # also covers simulation/ and ml_pipeline/
cd frontend && npm install && cd ..
```

## Run order
Data and the trained model are generated files, so rebuild them whenever the scenarios change.

```bash
# 1. Build the scenario matrix (about 600 scenarios on Net1, Net2, Net3) -> simulation/scenarios.json
python simulation/build_scenarios.py

# 2. Simulate every scenario -> data/raw_simulations/<network>/  (about 30 s; use --force to redo, --network net3, --only <id>)
python simulation/generate_dataset.py --force

# 3. Train the cause classifier on the 80% training scenarios -> ml_pipeline/models/, data/results/decision_rules.txt, split.json
python ml_pipeline/train.py

# 4. Evaluate on the 20% held-out test scenarios -> data/results/evaluation_summary.json
python ml_pipeline/evaluate.py

# 5. Start the backend (port 8000, docs at /docs)
cd backend && uvicorn main:app --port 8000

# 6. Start the dashboard (port 3000)
cd frontend && npm run dev
```

## Training and testing
All scenarios are split once into about 80% for learning and 20% for testing (`ml_pipeline/split.py`, fixed seed). The noise thresholds and the cause classifier use training scenarios only, and every reported result is measured on the unseen test scenarios. Near-copies (all leaks at one node, a scenario and its noisy twin) stay on the same side. The dashboard tags each scenario *Unseen test* or *Training*.

## What the system does
1. **Simulate** leaks, demand changes, hydrants, pump outages, reservoir head changes, tank levels, blocked pipes and ageing
   (`simulation/simulator.py`), with optional sensor noise.
2. **Detect**: a per-network noise threshold learned from normal runs, and a persistence rule (`ml_pipeline/detector.py`).
3. **Classify the cause** with features that use pressure, pipe flow and metered node demand (`ml_pipeline/features.py`, `classifier.py`).
   Key physics: *unaccounted flow = change in node flow balance - change in metered demand* is the leak flow.
4. **Localize** the leak by ranking junctions on unaccounted flow plus pressure drop (`ml_pipeline/localizer.py`) and report the error
   as pipe-graph distance (hops and metres).
5. **Show** everything in the dashboard: scenario picker, predicted cause with probabilities, Top-k leak locations, search region,
   affected area, per-node telemetry and an Evaluation tab.

See `SEMESTER_1_COMPLETION.md` for results and limitations.

## Dashboard
1. Open http://localhost:3000. Choose a network (Net1, Net2, Net3) and a scenario.
2. Click **Run ML Analysis**. Leaks show Top-k nodes in red; other events show the predicted cause and the affected area.
3. Untick "Node demands are metered" to see how much harder it is to separate demand changes from leaks without meters.
4. **Evaluation** tab shows the results tables (detection, localization, confusion matrix, unseen-network test).

## Database
The backend keeps the scenario catalog in SQLite (`backend/sql_app.db`, table `scenarios`), refreshed from the generated manifests at start-up.
