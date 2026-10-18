"use client";

import React, { useEffect, useMemo, useState } from 'react';
import ReactFlow, { Background, Controls, Node, Edge, useReactFlow, ReactFlowProvider } from 'reactflow';
import 'reactflow/dist/style.css';
import { fetchNetworkGraph } from '@/lib/api';
import { Eye, EyeOff, Info, Layers, MapPin, Search, Waves, X } from 'lucide-react';
import { FlowMetric, NodeMetric } from '@/lib/types';

interface NetworkMapProps {
  network: string;
  predictedLeaks: string[];
  affectedNodes?: string[];
  candidateRegion?: string[];
  nodeMetrics?: Record<string, NodeMetric>;
  flowMetrics?: Record<string, FlowMetric>;
  selectedNodeId?: string | null;
  onSelectNode?: (nodeId: string | null) => void;
  picking?: boolean;
  onCancelPicking?: () => void;
  highlightNode?: string;
}

interface RawNode { id: string | number; x: number; y: number; type: string }

function FlowContent({
  network, predictedLeaks, affectedNodes = [], candidateRegion = [], flowMetrics = {},
  selectedNodeId, onSelectNode, picking = false, onCancelPicking, highlightNode,
}: NetworkMapProps) {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [rawNodes, setRawNodes] = useState<RawNode[]>([]);
  const [showLabels, setShowLabels] = useState(false);
  const [animatePipes, setAnimatePipes] = useState(false);
  const [legendOpen, setLegendOpen] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const { fitView, setCenter } = useReactFlow();

  // Load the layout whenever another network is chosen
  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchNetworkGraph(network);
        if (!data.nodes || data.nodes.length === 0) return;
        setRawNodes(data.nodes);
        const xs = data.nodes.map((n: RawNode) => n.x);
        const ys = data.nodes.map((n: RawNode) => n.y);
        const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
        const rangeX = maxX - minX || 1, rangeY = maxY - minY || 1, size = 1500;
        setNodes(data.nodes.map((n: RawNode) => ({
          id: String(n.id),
          position: { x: ((n.x - minX) / rangeX) * size, y: size - ((n.y - minY) / rangeY) * size },
          data: { label: String(n.id), type: n.type },
        })));
        setEdges(data.edges.map((e: { id: string; source: string; target: string }) => ({
          id: String(e.id), source: String(e.source), target: String(e.target), type: 'straight',
        })));
        setTimeout(() => fitView({ duration: 400, padding: 0.15 }), 60);
      } catch (error) {
        console.error('Failed to load network graph', error);
      }
    };
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [network]);

  const styledNodes = useMemo(() => nodes.map((node) => {
    const isLeak = predictedLeaks.includes(node.id);
    const isTop = predictedLeaks[0] === node.id;
    const isSelected = selectedNodeId === node.id;
    const isAffected = affectedNodes.includes(node.id);
    const inRegion = candidateRegion.includes(node.id);
    const isHint = highlightNode === node.id;
    const type = String(node.data?.type || 'Junction').toLowerCase();
    const isReservoir = type.includes('reservoir');
    const isTank = type.includes('tank');

    let bg = 'var(--accent)';
    let border = 'var(--panel)';
    let size = 16;
    let radius = '50%';
    let shadow = 'none';
    let z = 1;
    let ring = 'transparent';

    if (isReservoir) { bg = '#14a36a'; size = 24; radius = '6px'; z = 5; }
    else if (isTank) { bg = '#8b5cf6'; size = 22; radius = '6px'; z = 5; }
    if (isAffected && !isReservoir && !isTank) { bg = 'var(--warn)'; size = 18; z = 3; }
    if (inRegion && !isLeak) { ring = 'var(--danger)'; z = 6; }
    if (isLeak) {
      bg = 'var(--danger)'; size = isTop ? 30 : 24; z = 10; ring = 'var(--danger)';
      shadow = '0 0 0 6px color-mix(in srgb, var(--danger) 25%, transparent)';
    }
    if (isHint) { ring = 'var(--accent)'; size = Math.max(size, 26); z = 12; }
    if (isSelected) { border = 'var(--ink)'; size = Math.max(size, 26); z = 20; }

    const showText = showLabels || isLeak || isSelected || isHint || isReservoir || isTank;
    return {
      ...node,
      style: {
        background: bg,
        border: `3px solid ${border}`,
        outline: ring === 'transparent' ? 'none' : `3px solid ${ring}`,
        outlineOffset: 1,
        borderRadius: radius,
        width: size,
        height: size,
        boxShadow: shadow,
        zIndex: z,
        cursor: 'pointer',
        padding: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        transition: 'all .15s ease',
      },
      data: {
        label: showText ? (
          <span style={{
            position: 'absolute', top: size + 4, left: '50%', transform: 'translateX(-50%)', whiteSpace: 'nowrap',
            fontSize: 12, fontWeight: 700, color: 'var(--ink)', background: 'color-mix(in srgb, var(--panel) 85%, transparent)',
            padding: '1px 5px', borderRadius: 6, pointerEvents: 'none',
          }}>{node.id}</span>
        ) : '',
      },
    };
  }), [nodes, predictedLeaks, affectedNodes, candidateRegion, selectedNodeId, showLabels, highlightNode]);

  const styledEdges = useMemo(() => edges.map((edge) => {
    const flow = flowMetrics[edge.id];
    const changed = flow && Math.abs(flow.flow_change) > 0.01;
    return {
      ...edge,
      animated: animatePipes,
      style: { stroke: changed ? 'var(--accent)' : 'var(--pipe)', strokeWidth: changed ? 3 : 1.8, opacity: changed ? 0.95 : 0.7 },
    };
  }), [edges, flowMetrics, animatePipes]);

  useEffect(() => {
    if (!selectedNodeId) return;
    const target = nodes.find((n) => n.id === selectedNodeId);
    if (target) setCenter(target.position.x, target.position.y, { zoom: 1.1, duration: 600 });
  }, [selectedNodeId, nodes, setCenter]);

  const hits = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return q ? rawNodes.filter((n) => String(n.id).toLowerCase().startsWith(q)).slice(0, 6) : [];
  }, [searchQuery, rawNodes]);

  const toolBtn = (on: boolean) =>
    `flex items-center gap-1.5 h-9 px-3 rounded-lg text-[13px] font-medium border transition-colors ${
      on ? 'bg-accent text-accentink border-accent' : 'bg-panel text-ink border-line hover:bg-panel2'}`;

  return (
    <div className="relative w-full h-full rounded-2xl overflow-hidden border border-line" style={{ background: 'var(--map-bg)' }}>
      {/* Toolbar */}
      <div className="absolute top-3 left-3 right-3 z-20 flex flex-wrap items-center gap-2 pointer-events-none">
        <div className="relative pointer-events-auto">
          <div className="flex items-center h-9 rounded-lg border border-line bg-panel px-2.5">
            <Search size={15} className="text-muted mr-2" />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Find node…"
              aria-label="Find a node by number"
              className="bg-transparent text-ink outline-none w-28 text-[13px] placeholder:text-muted"
            />
          </div>
          {hits.length > 0 && (
            <ul className="absolute left-0 top-full mt-1 w-44 rounded-lg border border-line bg-panel shadow-xl overflow-hidden">
              {hits.map((n) => (
                <li key={String(n.id)}>
                  <button
                    onClick={() => { onSelectNode?.(String(n.id)); setSearchQuery(''); }}
                    className="w-full text-left px-3 py-2 text-[13px] text-ink hover:bg-accentsoft"
                  >Node {n.id} <span className="text-muted">({n.type})</span></button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <button className={`pointer-events-auto ${toolBtn(showLabels)}`} onClick={() => setShowLabels(!showLabels)} aria-pressed={showLabels}>
          {showLabels ? <Eye size={15} /> : <EyeOff size={15} />} Node numbers
        </button>
        <button className={`pointer-events-auto ${toolBtn(animatePipes)}`} onClick={() => setAnimatePipes(!animatePipes)} aria-pressed={animatePipes}>
          <Waves size={15} /> Flow animation
        </button>
        <button className={`pointer-events-auto ${toolBtn(false)}`} onClick={() => fitView({ duration: 500, padding: 0.15 })}>
          <Layers size={15} /> Fit to screen
        </button>
      </div>

      {picking && (
        <div className="absolute top-16 left-1/2 -translate-x-1/2 z-30 flex items-center gap-3 rounded-xl bg-accent text-accentink px-4 py-2.5 shadow-xl text-[14px] font-medium">
          <MapPin size={18} /> Click a node on the map to choose where the leak is
          <button onClick={onCancelPicking} className="ml-1 p-1 rounded hover:bg-black/10" aria-label="Cancel picking"><X size={16} /></button>
        </div>
      )}

      <ReactFlow
        nodes={styledNodes}
        edges={styledEdges}
        onNodeClick={(_, node) => onSelectNode?.(node.id)}
        fitView
        minZoom={0.1}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        aria-label="Water network map"
      >
        <Background color="var(--map-grid)" gap={26} size={1.4} />
        <Controls showInteractive={false} />
      </ReactFlow>

      {/* Legend */}
      <div className="absolute bottom-3 left-3 z-20 rounded-xl border border-line bg-panel shadow-lg text-[13px] max-w-[270px]">
        <button onClick={() => setLegendOpen(!legendOpen)} className="w-full flex items-center justify-between gap-3 px-3 py-2 font-semibold text-ink" aria-expanded={legendOpen}>
          <span className="flex items-center gap-1.5"><Info size={15} /> Map key</span>
          <span className="text-muted text-xs">{legendOpen ? 'Hide' : 'Show'}</span>
        </button>
        {legendOpen && (
          <ul className="px-3 pb-3 space-y-1.5 text-ink">
            <li className="flex items-center gap-2"><i className="w-3.5 h-3.5 rounded-full" style={{ background: 'var(--accent)' }} /> Junction (water use point)</li>
            <li className="flex items-center gap-2"><i className="w-3.5 h-3.5 rounded-md" style={{ background: '#14a36a' }} /> Reservoir (water source)</li>
            <li className="flex items-center gap-2"><i className="w-3.5 h-3.5 rounded-md" style={{ background: '#8b5cf6' }} /> Storage tank</li>
            <li className="flex items-center gap-2"><i className="w-3.5 h-3.5 rounded-full" style={{ background: 'var(--warn)' }} /> Lost pressure</li>
            <li className="flex items-center gap-2"><i className="w-3.5 h-3.5 rounded-full" style={{ background: 'var(--danger)' }} /> Probable leak</li>
            <li className="flex items-center gap-2"><i className="w-3.5 h-3.5 rounded-full" style={{ background: 'var(--accent)', outline: '3px solid var(--danger)' }} /> Search region</li>
            <li className="flex items-center gap-2"><i className="w-5 h-1 rounded" style={{ background: 'var(--accent)' }} /> Pipe with changed flow</li>
          </ul>
        )}
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
