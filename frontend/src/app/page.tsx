"use client";

import React, { useState } from 'react';
import NetworkMap from '@/components/NetworkMap';
import { analyzeScenario } from '@/lib/api';
import { Activity, AlertTriangle, CheckCircle2, Play, Map, ChevronRight, Gauge } from 'lucide-react';

export default function Dashboard() {
  const [scenario, setScenario] = useState('leak_15');
  const [analyzing, setAnalyzing] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const data = await analyzeScenario(scenario);
      setResults(data);
      if (data.predicted_leaks && data.predicted_leaks.length > 0) {
        setSelectedNodeId(data.predicted_leaks[0].node_id);
      }
    } catch (error) {
      console.error("Analysis failed", error);
    } finally {
      setAnalyzing(false);
    }
  };

  // Show Top-K predicted leak candidate nodes on the map
  const predictedLeaks = results?.predicted_leaks?.map((p: any) => p.node_id) || [];

  return (
    <div className="flex h-screen bg-slate-950 text-slate-200 font-sans">
      
      {/* Sidebar Controls */}
      <aside className="w-80 bg-slate-900 border-r border-slate-800 flex flex-col z-10">
        <div className="p-6 border-b border-slate-800">
          <div className="flex items-center gap-3 text-blue-400 mb-2">
            <Activity size={28} />
            <h1 className="text-xl font-bold tracking-tight text-white">AquaGuard ML</h1>
          </div>
          <p className="text-slate-400 text-xs">Intelligent Leak Detection & Localization</p>
        </div>

        <div className="p-6 flex-1 overflow-y-auto">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">Simulation Controls</h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Network Model</label>
              <select className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none">
                <option value="net3">Net3 (Benchmark Network)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs text-slate-400 mb-1">Select Hydraulic Scenario</label>
              <select 
                value={scenario}
                onChange={(e) => setScenario(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
              >
                <option value="baseline">Baseline (Normal Operations)</option>
                <option value="leak_3">Leak at Node 3</option>
                <option value="leak_15">Leak at Node 15</option>
                <option value="leak_115">Leak at Node 115</option>
                <option value="leak_121">Leak at Node 121</option>
                <option value="demand_up_15">Demand increase at Node 15</option>
                <option value="demand_down_15">Demand decrease at Node 15</option>
                <option value="pump_outage_335">Pump 335 outage</option>
              </select>
            </div>

            <button 
              onClick={handleAnalyze}
              disabled={analyzing}
              className="w-full mt-4 bg-blue-600 hover:bg-blue-500 text-white rounded-lg py-3 px-4 text-sm font-medium transition-all shadow-lg shadow-blue-600/30 flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {analyzing ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <Play size={16} />
              )}
              {analyzing ? 'Processing Simulation Data...' : 'Run ML Analysis'}
            </button>
          </div>

          {/* Results Section */}
          {results && (
            <div className="mt-8 space-y-4">
              <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">Analysis Results</h2>
              
              <div className={`p-4 rounded-xl border ${results.has_anomaly ? 'bg-red-900/20 border-red-800/50' : 'bg-green-900/20 border-green-800/50'}`}>
                <div className="flex items-center gap-3">
                  {results.has_anomaly ? (
                    <AlertTriangle className="text-red-400" size={24} />
                  ) : (
                    <CheckCircle2 className="text-green-400" size={24} />
                  )}
                  <div>
                    <h3 className={`font-semibold ${results.has_anomaly ? 'text-red-400' : 'text-green-400'}`}>
                      {results.has_anomaly ? 'Anomaly Detected' : 'System Normal'}
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {results.has_anomaly ? 'Pressure deviation exceeds safety threshold.' : 'Hydraulic behavior matches baseline.'}
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-slate-800 rounded-xl p-4 border border-slate-700 space-y-2">
                <h3 className="text-sm font-semibold text-white">System explanation</h3>
                <p className="text-xs text-amber-300">{results.event_assessment}</p>
                {(results.explanation || []).map((line: string, index: number) => (
                  <p key={index} className="text-xs text-slate-300">{line}</p>
                ))}
                {results.scenario_truth && Object.keys(results.scenario_truth).length > 0 && (
                  <div className="pt-2 border-t border-slate-700 text-xs text-slate-400">
                    <span className="font-semibold text-slate-200">Simulation ground truth (evaluation only): </span>
                    {Object.entries(results.scenario_truth).map(([key, value]) => `${key}: ${value}`).join(' · ')}
                  </div>
                )}
              </div>

              {results.has_anomaly && results.predicted_leaks.length > 0 && (
                <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
                  <h3 className="text-sm font-medium text-slate-200 mb-3 flex items-center gap-2">
                    <Map size={16} className="text-blue-400"/>
                    Probable Leak Locations
                  </h3>
                  <div className="space-y-2">
                    {results.predicted_leaks.map((p: any, idx: number) => {
                      const isSelected = selectedNodeId === p.node_id;
                      return (
                        <button 
                          key={idx} 
                          onClick={() => setSelectedNodeId(p.node_id)}
                          className={`w-full flex items-center justify-between p-2.5 rounded-lg border transition-all text-left ${
                            isSelected 
                              ? 'bg-blue-600/20 border-blue-500 shadow-md ring-1 ring-blue-500' 
                              : 'bg-slate-900 border-slate-700/60 hover:bg-slate-800'
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
                              idx === 0 ? 'bg-red-500 text-white' : 'bg-slate-700 text-slate-300'
                            }`}>
                              {idx + 1}
                            </span>
                            <div>
                              <p className="text-sm font-medium text-white">Node {p.node_id}</p>
                      <p className="text-[10px] text-slate-400 font-mono">Heuristic score: {p.confidence_score.toFixed(1)}</p>
                            </div>
                          </div>
                          <ChevronRight size={16} className="text-slate-400" />
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </aside>

      {/* Main Visualization Area */}
      <main className="flex-1 p-6 flex flex-col">
        <header className="mb-4 flex justify-between items-center">
          <div>
            <h2 className="text-2xl font-bold text-white">Network Topology & Telemetry Inspection</h2>
            <p className="text-slate-400 text-xs mt-0.5">Click any junction node to inspect real-time pressure, elevation, and pipe flow rate details.</p>
          </div>
        </header>

        <div className="flex-1 rounded-xl shadow-2xl relative bg-slate-900 flex items-center justify-center border border-slate-800">
           <NetworkMap 
             predictedLeaks={predictedLeaks}
             nodeMetrics={results?.node_metrics}
             flowMetrics={results?.flow_metrics}
             selectedNodeId={selectedNodeId}
             onSelectNode={(id) => setSelectedNodeId(id)}
           />
        </div>
      </main>

    </div>
  );
}

