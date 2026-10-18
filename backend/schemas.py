from pydantic import BaseModel
from typing import List, Dict, Optional

class NodeBase(BaseModel):
    id: str
    x: float
    y: float
    type: str
    elevation: Optional[float] = 0.0

class EdgeBase(BaseModel):
    id: str
    source: str
    target: str

class NetworkGraph(BaseModel):
    nodes: List[NodeBase]
    edges: List[EdgeBase]

class PredictionResult(BaseModel):
    node_id: str
    confidence_score: float
    pressure_drop: float = 0.0
    flow_divergence: float = 0.0

class NodeMetric(BaseModel):
    node_id: str
    node_type: str
    elevation: float
    baseline_pressure: float
    current_pressure: float
    pressure_drop: float
    flow_divergence: float = 0.0
    composite_score: float = 0.0
    status: str
    connected_pipes: List[str]
    baseline_series: List[float] = []
    current_series: List[float] = []

class FlowMetric(BaseModel):
    link_id: str
    baseline_flow: float
    current_flow: float
    flow_change: float

class AnalysisResponse(BaseModel):
    has_anomaly: bool
    event_assessment: str = "cause uncertain"
    scenario_truth: Dict[str, str] = {}
    explanation: List[str] = []
    peak_time: Optional[str] = None
    max_pressure_drop: float = 0.0
    predicted_leaks: List[PredictionResult]
    node_metrics: Dict[str, NodeMetric] = {}
    flow_metrics: Dict[str, FlowMetric] = {}
    
class SimulationRunBase(BaseModel):
    scenario_name: str
    is_baseline: bool
    leak_node: Optional[str] = None
    pressures_csv_path: str
    flows_csv_path: str

class SimulationRunResponse(SimulationRunBase):
    id: int

    class Config:
        from_attributes = True

