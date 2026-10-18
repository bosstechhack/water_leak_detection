export interface Scenario {
  id: string;
  network: string;
  name: string;
  group: string;
  event_class: string;
  truth_nodes: string[];
  params: {
    category: string;
    noisy: boolean;
    hidden_by: string | null;
    node: string | null;
    size: number | null;
    size_label: string | null;
    start_hour: number | null;
    split?: 'train' | 'test' | 'reference';
    kind?: string;
    factor?: number;
    pump?: string;
    reservoir?: string;
    tank?: string;
    pipe?: string;
    delta_m?: number;
    fraction?: number;
  };
}

export interface Prediction {
  node_id: string;
  confidence_score: number;
  pressure_drop: number;
  flow_divergence: number;
}

export interface NodeMetric {
  node_id: string;
  node_type: string;
  elevation: number;
  baseline_pressure: number;
  current_pressure: number;
  pressure_drop: number;
  flow_divergence: number;
  composite_score: number;
  status: string;
  connected_pipes: string[];
  baseline_series: number[];
  current_series: number[];
}

export interface FlowMetric {
  link_id: string;
  baseline_flow: number;
  current_flow: number;
  flow_change: number;
}

export interface Analysis {
  network: string;
  split: 'train' | 'test' | 'reference';
  event_class: string | null;
  event_label: string | null;
  probabilities: Record<string, number>;
  features: Record<string, number>;
  detection: Record<string, number>;
  worst_node: string | null;
  candidate_region: string[];
  affected_nodes: string[];
  localization_error_hops: number | null;
  has_anomaly: boolean;
  scenario_truth: Record<string, string>;
  explanation: string[];
  max_pressure_drop: number;
  predicted_leaks: Prediction[];
  node_metrics: Record<string, NodeMetric>;
  flow_metrics: Record<string, FlowMetric>;
}

export interface NetworkInfo {
  id: string;
  name: string;
  junctions: number;
  scenarios: number;
}
