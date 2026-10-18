"use client";

import React, { useEffect, useState, useMemo } from 'react';
import ReactFlow, { Background, Controls, Node, Edge, useReactFlow, ReactFlowProvider } from 'reactflow';
import 'reactflow/dist/style.css';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { fetchNetworkGraph } from '@/lib/api';
import { Search, Eye, EyeOff, Activity, Gauge, ArrowDownRight, Layers, X, Sparkles, Droplets } from 'lucide-react';

interface NetworkMapProps {
  predictedLeaks: string[];
  nodeMetrics?: Record<string, any>;
  flowMetrics?: Record<string, any>;
  selectedNodeId?: string | null;
  onSelectNode?: (nodeId: string | null) => void;
}

function FlowContent({ 
  predictedLeaks, 
  nodeMetrics = {}, 
  flowMetrics = {}, 
  selectedNodeId, 
  onSelectNode 
}: NetworkMapProps) {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [rawNodes, setRawNodes] = useState<any[]>([]);
  const [showLabels, setShowLabels] = useState<boolean>(true);
  const [animatePipes, setAnimatePipes] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  
  const { fitView, setCenter } = useReactFlow();

  // Load topology once
  useEffect(() => {
    const loadGraph = async () => {
      try {
        const data = await fetchNetworkGraph();
        if (!data.nodes || data.nodes.length === 0) return;
        setRawNodes(data.nodes);

        const xCoords = data.nodes.map((n: any) => n.x);
        const yCoords = data.nodes.map((n: any) => n.y);
        const minX = Math.min(...xCoords);
        const maxX = Math.max(...xCoords);
        const minY = Math.min(...yCoords);
        const maxY = Math.max(...yCoords);

        const rangeX = maxX - minX || 1;
        const rangeY = maxY - minY || 1;
        const targetSize = 2500;

        const rfNodes = data.nodes.map((n: any) => {
          const idStr = String(n.id);
          const posX = ((n.x - minX) / rangeX) * targetSize;
          const posY = targetSize - ((n.y - minY) / rangeY) * targetSize;

          return {
            id: idStr,
            position: { x: posX, y: posY },
            data: { label: idStr, rawX: n.x, rawY: n.y, type: n.type },
          };
        });

        const rfEdges = data.edges.map((e: any) => ({
          id: String(e.id),
          source: String(e.source),
          target: String(e.target),
          type: 'straight',
        }));

        setNodes(rfNodes);
        setEdges(rfEdges);
      } catch (error) {
        console.error("Failed to load network graph", error);
      }
    };
    loadGraph();
  }, []);

  // Update styled nodes and edges based on predictedLeaks, selection, showLabels, animatePipes
  const styledNodes = useMemo(() => {
    return nodes.map((node) => {
      const isLeak = predictedLeaks.includes(node.id);
      const isSelected = selectedNodeId === node.id;
      const metric = nodeMetrics[node.id];
      const hasDrop = metric && metric.pressure_drop > 3.0;

      const nodeType = String(node.data?.type || metric?.node_type || 'Junction').toLowerCase();
      const isReservoir = nodeType.includes('reservoir');
      const isTank = nodeType.includes('tank');

      let bgColor = '#3b82f6'; // default blue junction
      let borderColor = '#60a5fa';
      let shadow = '0 0 6px rgba(59, 130, 246, 0.4)';
      let size = 18;
      let zIndex = 1;
      let borderRadius = '50%';

      if (isReservoir) {
        bgColor = '#10b981'; // Emerald green for Reservoirs
        borderColor = '#6ee7b7';
        shadow = '0 0 12px rgba(16, 185, 129, 0.7)';
        size = 26;
        borderRadius = '6px'; // Square / Diamond shape for Reservoir
        zIndex = 8;
      } else if (isTank) {
        bgColor = '#8b5cf6'; // Purple for Tanks
        borderColor = '#c4b5fd';
        shadow = '0 0 12px rgba(139, 92, 246, 0.7)';
        size = 24;
        borderRadius = '8px'; // Rounded cylinder box for Tanks
        zIndex = 7;
      }

      if (isLeak) {
        bgColor = '#ef4444'; // glowing red
        borderColor = '#fca5a5';
        shadow = '0 0 25px rgba(239, 68, 68, 1)';
        size = 32;
        borderRadius = '50%';
        zIndex = 10;
      } else if (hasDrop && !isReservoir && !isTank) {
        bgColor = '#f59e0b'; // amber drop warning
        borderColor = '#fde68a';
        shadow = '0 0 15px rgba(245, 158, 11, 0.8)';
        size = 24;
        zIndex = 5;
      }

      if (isSelected) {
        borderColor = '#ffffff';
        shadow = '0 0 30px rgba(255, 255, 255, 1)';
        size = Math.max(size, 30);
        zIndex = 20;
      }

      return {
        ...node,
        style: {
          background: bgColor,
          color: 'white',
          border: `3px solid ${borderColor}`,
          borderRadius: borderRadius,
          width: size,
          height: size,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          fontSize: showLabels ? '10px' : '0px',
          fontWeight: 'bold',
          boxShadow: shadow,
          zIndex: zIndex,
          transition: 'all 0.2s ease-in-out',
          cursor: 'pointer',
        },
        data: {
          label: showLabels ? node.id : '',
        }
      };
    });
  }, [nodes, predictedLeaks, selectedNodeId, nodeMetrics, showLabels]);

  const styledEdges = useMemo(() => {
    return edges.map((edge) => {
      const flow = flowMetrics[edge.id];
      const isHighFlowChange = flow && Math.abs(flow.flow_change) > 0.1;

      return {
        ...edge,
        animated: animatePipes,
        style: {
          stroke: isHighFlowChange ? '#38bdf8' : '#475569',
          strokeWidth: isHighFlowChange ? 3 : 2,
          opacity: 0.8,
        }
      };
    });
  }, [edges, flowMetrics, animatePipes]);

  const handleNodeClick = (_: any, node: Node) => {
    if (onSelectNode) {
      onSelectNode(node.id);
    }
  };

  // Center on node if selected
  useEffect(() => {
    if (selectedNodeId) {
      const targetNode = nodes.find(n => n.id === selectedNodeId);
      if (targetNode) {
        setCenter(targetNode.position.x, targetNode.position.y, { zoom: 1.2, duration: 800 });
      }
    }
  }, [selectedNodeId, nodes, setCenter]);

  // Selected Node detailed metric
  const activeMetric = selectedNodeId ? nodeMetrics[selectedNodeId] : null;

  // Filtered nodes for search dropdown
  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];
    return rawNodes.filter(n => String(n.id).toLowerCase().includes(searchQuery.toLowerCase())).slice(0, 5);
  }, [searchQuery, rawNodes]);

  return (
    <div className="w-full h-full bg-slate-950 rounded-xl overflow-hidden border border-slate-800 shadow-2xl relative">
      
      {/* Top Customization Toolbar */}
      <div className="absolute top-4 left-4 z-20 flex flex-wrap items-center gap-3 bg-slate-900/90 p-2.5 rounded-xl border border-slate-800 backdrop-blur-md shadow-lg">
        
        {/* Node Search Bar */}
        <div className="relative">
          <div className="flex items-center bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs">
            <Search size={14} className="text-slate-400 mr-2" />
            <input 
              type="text"
              placeholder="Search Node ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-transparent text-white outline-none w-28 placeholder:text-slate-500"
            />
          </div>
          {searchResults.length > 0 && (
            <div className="absolute left-0 top-full mt-1 w-full bg-slate-800 border border-slate-700 rounded-lg shadow-xl overflow-hidden z-30">
              {searchResults.map(n => (
                <button
                  key={n.id}
                  onClick={() => {
                    if (onSelectNode) onSelectNode(String(n.id));
                    setSearchQuery('');
                  }}
                  className="w-full text-left px-3 py-1.5 text-xs text-slate-200 hover:bg-blue-600 hover:text-white transition-colors"
                >
                  Node {n.id} ({n.type})
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="h-4 w-px bg-slate-700 mx-1" />

        {/* Customization Toggles */}
        <button
          onClick={() => setShowLabels(!showLabels)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${showLabels ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-slate-200'}`}
          title="Toggle node labels"
        >
          {showLabels ? <Eye size={14} /> : <EyeOff size={14} />}
          <span>Labels</span>
        </button>

        <button
          onClick={() => setAnimatePipes(!animatePipes)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${animatePipes ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-slate-200'}`}
          title="Toggle pipe flow animation"
        >
          <Activity size={14} />
          <span>Flow Animation</span>
        </button>

        <button
          onClick={() => fitView({ duration: 800 })}
          className="flex items-center gap-1 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium transition-all"
        >
          <Layers size={14} />
          <span>Fit View</span>
        </button>
      </div>

      {/* Main React Flow Graph Canvas */}
      <ReactFlow 
        nodes={styledNodes} 
        edges={styledEdges}
        onNodeClick={handleNodeClick}
        fitView
        attributionPosition="bottom-left"
      >
        <Background color="#1e293b" gap={20} size={1} />
        <Controls className="bg-slate-900 border-slate-800 text-white fill-white shadow-xl" />
      </ReactFlow>

      {/* Detailed Node Inspection Panel (Floating Card on Top Right) */}
      {selectedNodeId && (
        <div className="absolute top-4 right-4 z-30 w-80 bg-slate-900/95 border border-slate-700/80 rounded-2xl p-5 shadow-2xl backdrop-blur-lg text-slate-200 animate-in fade-in slide-in-from-top-4 duration-300">
          <div className="flex justify-between items-start mb-3 border-b border-slate-800 pb-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-500 animate-ping" />
                <h3 className="text-lg font-bold text-white tracking-tight">Node {selectedNodeId}</h3>
              </div>
              <p className="text-slate-400 text-xs mt-0.5 font-mono">
                {activeMetric?.node_type || 'Junction'} • Elev: {activeMetric?.elevation ?? 0}m
              </p>
            </div>
            <button 
              onClick={() => onSelectNode && onSelectNode(null)}
              className="p-1 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
            >
              <X size={18} />
            </button>
          </div>

          {activeMetric ? (
            <div className="space-y-4">
              
              {/* Status Badge */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">Hydraulic Status</span>
                <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
                  predictedLeaks.includes(selectedNodeId)
                    ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                    : activeMetric.pressure_drop > 3.0
                    ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                    : 'bg-green-500/20 text-green-400 border border-green-500/40'
                }`}>
                  {activeMetric.status}
                </span>
              </div>

              {/* Pressure & Flow Telemetry Metrics */}
              <div className="grid grid-cols-2 gap-2 bg-slate-950 p-3 rounded-xl border border-slate-800/80">
                <div>
                  <div className="flex items-center gap-1 text-slate-400 text-[11px] mb-1">
                    <Gauge size={12} className="text-blue-400" />
                    <span>Pressure Head</span>
                  </div>
                  <p className="text-base font-extrabold text-white font-mono">{activeMetric.current_pressure} <span className="text-xs font-normal text-slate-400">m</span></p>
                  <p className="text-[10px] text-slate-500 font-mono">Base: {activeMetric.baseline_pressure}m (ΔP: -{activeMetric.pressure_drop}m)</p>
                </div>
                <div>
                  <div className="flex items-center gap-1 text-slate-400 text-[11px] mb-1">
                    <Droplets size={12} className="text-cyan-400" />
                    <span>Mass Imbalance</span>
                  </div>
                  <p className={`text-base font-extrabold font-mono ${activeMetric.flow_divergence > 0.001 ? 'text-cyan-400' : 'text-slate-300'}`}>
                    +{activeMetric.flow_divergence} <span className="text-xs font-normal text-slate-400">m³/s</span>
                  </p>
                  <p className="text-[10px] text-slate-500 font-mono">
                    {activeMetric.flow_divergence > 0.001 ? '⚡ Net Flow Loss' : 'Balanced (0.0 m³/s)'}
                  </p>
                </div>
              </div>

              {/* Composite Score Card */}
              <div className="bg-slate-950/80 p-2.5 rounded-xl border border-slate-800/80 flex items-center justify-between">
                <div>
                  <p className="text-[11px] text-slate-400">Heuristic leak score (ΔP + 50·ΔQ)</p>
                  <p className="text-xs text-slate-500 font-mono">
                    {activeMetric.pressure_drop} + (50 × {activeMetric.flow_divergence})
                  </p>
                </div>
                <span className={`text-sm font-black font-mono px-2.5 py-1 rounded-lg ${
                  predictedLeaks.includes(selectedNodeId) 
                    ? 'bg-red-500/20 text-red-400 border border-red-500/40' 
                    : 'bg-slate-800 text-slate-300'
                }`}>
                  {activeMetric.composite_score?.toFixed(2) ?? activeMetric.pressure_drop}
                </span>
              </div>

              {/* 24-Hour Pressure Chart */}
              {activeMetric.baseline_series && activeMetric.current_series && activeMetric.baseline_series.length > 0 && (
                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800/80">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
                      <Activity size={14} className="text-blue-400" />
                      24-Hour Pressure Profile
                    </h4>
                    <span className="text-[10px] text-slate-500 font-mono">Hour 0 – 24</span>
                  </div>
                  <div className="h-28 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={activeMetric.baseline_series.map((v: number, i: number) => ({
                          hour: i,
                          baseline: v,
                          current: activeMetric.current_series[i]
                        }))}
                        margin={{ top: 5, right: 5, left: -20, bottom: 0 }}
                      >
                        <XAxis dataKey="hour" stroke="#64748b" fontSize={10} tickFormatter={(val) => `${val}h`} />
                        <YAxis stroke="#64748b" fontSize={10} domain={['auto', 'auto']} />
                        <Tooltip 
                          contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', fontSize: '11px', borderRadius: '8px' }}
                          itemStyle={{ padding: 0 }}
                        />
                        <Line type="monotone" dataKey="baseline" name="Baseline (m)" stroke="#3b82f6" strokeWidth={2} dot={false} />
                        <Line type="monotone" dataKey="current" name="Current (m)" stroke="#ef4444" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {/* Connected Pipes with Flow Details */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
                    <Droplets size={14} className="text-blue-400" />
                    Connected Pipes Flow ({activeMetric.connected_pipes?.length || 0})
                  </h4>
                  <span className="text-[10px] text-slate-500 font-mono">Current | Base | ΔQ</span>
                </div>
                <div className="max-h-32 overflow-y-auto space-y-1.5 pr-1">
                  {activeMetric.connected_pipes?.map((pipeId: string) => {
                    const flow = flowMetrics[pipeId];
                    return (
                      <div key={pipeId} className="flex justify-between items-center bg-slate-950 p-2 rounded-lg text-xs font-mono border border-slate-800/50">
                        <span className="text-slate-300 font-semibold">Pipe {pipeId}</span>
                        {flow ? (
                          <div className="text-right">
                            <span className="text-cyan-400 font-bold">{flow.current_flow} m³/s</span>
                            <span className={`text-[10px] ml-2 ${flow.flow_change > 0 ? 'text-amber-400' : 'text-slate-500'}`}>
                              ({flow.flow_change > 0 ? `+${flow.flow_change}` : flow.flow_change})
                            </span>
                          </div>
                        ) : (
                          <span className="text-slate-500">Connected</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

            </div>
          ) : (
            <div className="py-4 text-center text-xs text-slate-500">
              Run ML analysis to view detailed pressure telemetry for Node {selectedNodeId}.
            </div>
          )}
        </div>
      )}

      {/* Map Legend */}
      <div className="absolute bottom-4 left-4 bg-slate-900/90 p-4 rounded-xl border border-slate-800 backdrop-blur-md shadow-xl text-xs">
        <h4 className="text-white font-semibold mb-2.5">Map Legend</h4>
        <div className="flex items-center gap-2 mb-2">
          <div className="w-3.5 h-3.5 rounded-full bg-blue-500 border border-blue-400 shadow-[0_0_6px_rgba(59,130,246,0.5)]"></div>
          <span className="text-slate-300">Junction</span>
        </div>
        <div className="flex items-center gap-2 mb-2">
          <div className="w-3.5 h-3.5 rounded-md bg-emerald-500 border border-emerald-300 shadow-[0_0_6px_rgba(16,185,129,0.5)]"></div>
          <span className="text-slate-300">Reservoir (River / Lake)</span>
        </div>
        <div className="flex items-center gap-2 mb-2">
          <div className="w-3.5 h-3.5 rounded-md bg-purple-500 border border-purple-300 shadow-[0_0_6px_rgba(139,92,246,0.5)]"></div>
          <span className="text-slate-300">Tank</span>
        </div>
        <div className="flex items-center gap-2 mb-2">
          <div className="w-3.5 h-3.5 rounded-full bg-amber-500 border border-amber-300 shadow-[0_0_8px_rgba(245,158,11,0.8)]"></div>
          <span className="text-slate-300">Anomalous Drop</span>
        </div>
        <div className="flex items-center gap-2 mb-2">
          <div className="w-3.5 h-3.5 rounded-full bg-red-500 border border-red-300 shadow-[0_0_12px_rgba(239,68,68,0.9)] animate-pulse"></div>
          <span className="text-slate-300 font-medium text-red-400">Predicted Leak</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-1 bg-slate-500"></div>
          <span className="text-slate-400">Pipe Connection</span>
        </div>
      </div>

    </div>
  );
}

export default function NetworkMap(props: NetworkMapProps) {
  return (
    <ReactFlowProvider>
      <FlowContent {...props} />
    </ReactFlowProvider>
  );
}
