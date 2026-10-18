# Intelligent Water Network Leak Detection & Localization

This repository contains the Semester 1 deliverable for the BTP Project. It provides a software-based hydraulic anomaly detection and leak localization system using EPANET/WNTR, Scikit-Learn, FastAPI, and Next.js.

## Prerequisites
- Python 3.9+
- Node.js 18+

## Setup & Running the Project

### 1. Generate Simulation Data
The system uses WNTR to simulate the EPANET Net3 benchmark. Edit `simulation/scenarios.json` to add or change a scenario, then run the generator once; each scenario is simulated from a fresh network model.
```bash
cd simulation
pip install -r requirements.txt
python generate_dataset.py
```
This writes pressure/flow CSV files and `data/raw_simulations/scenarios.csv`, which records the simulation ground truth. The configured cases include four leaks, demand increase/decrease, and a pump outage. Confirm the configured node and pump IDs against the chosen `.inp` model before relying on results.

### 2. Evaluate the Detection Baseline
From the project root, run:
```bash
venv/Scripts/python.exe ml_pipeline/evaluate.py
```
The script writes `data/raw_simulations/evaluation_results.csv` and reports leak Top-1/Top-5 localization and false alarms on non-leak scenarios. These are simulation results, not evidence of real-world sensor performance.

### 3. Start the Backend API (FastAPI)
The backend serves network topology and runs the ML inference on the simulation data.
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
*The API will be available at http://localhost:8000. You can view the docs at http://localhost:8000/docs.*

### 4. Start the Frontend Dashboard (Next.js)
The frontend is an interactive dashboard that visualizes the network and highlights predicted leaks.
```bash
cd frontend
npm install
npm run dev
```
*The dashboard will be available at http://localhost:3000.*

## How to use the Dashboard
1. Open http://localhost:3000.
2. The network topology (Net3) will render in the main view.
3. In the sidebar, select a scenario (e.g., "Leak at Node 15").
4. Click **Run ML Analysis**.
5. The system will process the time-series data from that scenario, detect anomalies (pressure drops), localize the leak, and highlight the predicted location on the map.
