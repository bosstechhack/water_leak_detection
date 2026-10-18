"use client";

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { BookOpen, BarChart3, Droplets, Map as MapIcon, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, Play } from 'lucide-react';
import NetworkMap from '@/components/NetworkMap';
import ScenarioPicker from '@/components/ScenarioPicker';
import ResultView from '@/components/ResultView';
import PerformanceView from '@/components/PerformanceView';
import GuideView from '@/components/GuideView';
import ThemeToggle from '@/components/ThemeToggle';
import { analyzeScenario, fetchNetworks, fetchScenarios } from '@/lib/api';
import { Analysis, NetworkInfo, Scenario } from '@/lib/types';

type View = 'investigate' | 'performance' | 'guide';

/** True on screens at least 1024px wide, so only one layout is mounted at a time. */
function useIsDesktop() {
  const [desktop, setDesktop] = useState(true);
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)');
    const update = () => setDesktop(mq.matches);
    update();
    mq.addEventListener('change', update);
    return () => mq.removeEventListener('change', update);
  }, []);
  return desktop;
}

const TABS: { id: View; label: string; icon: React.ReactNode }[] = [
  { id: 'investigate', label: 'Investigate', icon: <MapIcon size={17} /> },
  { id: 'performance', label: 'Performance', icon: <BarChart3 size={17} /> },
  { id: 'guide', label: 'Guide', icon: <BookOpen size={17} /> },
];

export default function Dashboard() {
  const [view, setView] = useState<View>('investigate');
  const [networks, setNetworks] = useState<NetworkInfo[]>([]);
  const [network, setNetwork] = useState('net3');
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [category, setCategory] = useState('leak');
  const [scenarioId, setScenarioId] = useState('');
  const [leakNode, setLeakNode] = useState('');
  const [picking, setPicking] = useState(false);
  const [useMeters, setUseMeters] = useState(true);
  const [splitFilter, setSplitFilter] = useState<'test' | 'train' | 'all'>('test');
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [nodeSignal, setNodeSignal] = useState(0);
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const isDesktop = useIsDesktop();

  useEffect(() => {
    fetchNetworks().then(setNetworks).catch(() => setError('Cannot reach the server at http://localhost:8000. Start the backend, then reload.'));
  }, []);

  useEffect(() => {
    setResults(null);
    setSelectedNode(null);
    setLeakNode('');
    fetchScenarios(network).then(setScenarios).catch(() => setScenarios([]));
  }, [network]);

  // Ready-made examples so a first-time user can see something in one click
  const examples = useMemo(() => {
    const pool = scenarios.filter((s) => s.params.split === 'test' || s.params.split === 'reference');
    const plainLeaks = pool.filter((s) => s.params.category === 'leak' && !s.params.noisy && !s.params.hidden_by && s.params.size_label === 'Medium' && (s.params.start_hour ?? 12) === 12);
    const first = (fn: (s: Scenario) => boolean) => pool.find(fn);
    return [
      { label: 'A leak at one node', hint: 'Find where it is', s: plainLeaks[Math.floor(plainLeaks.length / 2)] },
      { label: 'A leak hidden behind a demand surge', hint: 'The hard case', s: first((s) => s.params.hidden_by === 'demand') },
      { label: 'A pump stops', hint: 'Not a leak', s: first((s) => s.params.kind === 'pump_outage') },
      { label: 'Everyone uses more water', hint: 'Not a leak', s: first((s) => s.params.kind === 'global_demand' && (s.params.factor ?? 1) > 1) },
      { label: 'A pipe is blocked', hint: 'Not a leak', s: first((s) => s.params.category === 'valve_block') },
      { label: 'A normal day', hint: 'No problem', s: first((s) => s.params.category === 'normal') },
    ].filter((e) => e.s) as { label: string; hint: string; s: Scenario }[];
  }, [scenarios]);

  const run = useCallback(async (id?: string) => {
    const target = id || scenarioId;
    if (!target) return;
    const sc = scenarios.find((s) => s.id === target);
    if (sc) { setCategory(sc.params.category); setScenarioId(sc.id); if (sc.params.split === 'train' && splitFilter === 'test') setSplitFilter('all'); }
    setRunning(true);
    setError(null);
    setPicking(false);
    try {
      const data: Analysis = await analyzeScenario(target, useMeters);
      setResults(data);
      setRightOpen(true);
      setSelectedNode(data.predicted_leaks?.length ? data.predicted_leaks[0].node_id : null);
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ? `Analysis failed: ${detail}` : 'Analysis failed. Check that the backend is running and the model is trained (ml_pipeline/train.py).');
    } finally {
      setRunning(false);
    }
  }, [scenarioId, scenarios, useMeters, splitFilter]);

  const handleMapNode = (id: string | null) => {
    if (id && picking) {
      setLeakNode(id);
      setCategory('leak');
      setPicking(false);
      return;
    }
    setSelectedNode(id);
    if (id && results) { setNodeSignal((n) => n + 1); setRightOpen(true); }
  };

  const gridCols = `${leftOpen ? '360px' : '0px'} minmax(0,1fr) ${rightOpen ? '420px' : '0px'}`;

  return (
    <div className="flex flex-col min-h-screen lg:h-screen bg-bg text-ink">
      {/* Header */}
      <header className="flex flex-wrap items-center gap-3 px-4 sm:px-6 py-3 border-b border-line bg-panel">
        <div className="flex items-center gap-3 mr-auto">
          <span className="w-10 h-10 rounded-xl bg-accent text-accentink flex items-center justify-center"><Droplets size={22} /></span>
          <div className="leading-tight">
            <h1 className="text-[18px] font-bold text-ink">LeakLens</h1>
            <p className="text-[12px] text-muted">Water Leak Localization System</p>
          </div>
        </div>
        <nav aria-label="Sections" className="flex gap-1 p-1 rounded-xl bg-panel2">
          {TABS.map((t) => (
            <button key={t.id} onClick={() => setView(t.id)} aria-current={view === t.id ? 'page' : undefined}
              className={`flex items-center gap-2 h-10 px-3 sm:px-4 rounded-lg text-[14px] font-semibold ${view === t.id ? 'bg-panel text-ink shadow' : 'text-muted hover:text-ink'}`}>
              {t.icon}<span className="hidden sm:inline">{t.label}</span>
            </button>
          ))}
        </nav>
        <ThemeToggle />
      </header>

      {error && (
        <div role="alert" className="px-4 sm:px-6 py-2.5 bg-warnsoft text-warn text-[14px] font-medium border-b border-line">{error}</div>
      )}

      {view === 'performance' && <main className="flex-1 overflow-y-auto"><PerformanceView /></main>}
      {view === 'guide' && <main className="flex-1 overflow-y-auto"><GuideView /></main>}

      {view === 'investigate' && (
        <main className="flex-1 min-h-0 flex flex-col">
          {isDesktop ? (
          <div className="grid min-h-0 gap-4 flex-1 p-4" style={{ gridTemplateColumns: gridCols }}>
            <aside className={`min-h-0 overflow-y-auto rounded-2xl border border-line bg-panel p-4 ${leftOpen ? '' : 'hidden'}`}>
              <ScenarioPicker {...{ networks, network, scenarios, category, selectedId: scenarioId, leakNode, picking, useMeters, running, splitFilter }}
                onNetwork={setNetwork} onCategory={setCategory} onSelect={setScenarioId} onRun={run}
                onLeakNode={setLeakNode} onPicking={setPicking} onUseMeters={setUseMeters} onSplitFilter={setSplitFilter} />
            </aside>

            <section className="min-h-0 relative">
              <NetworkMap network={network} predictedLeaks={results?.predicted_leaks.map((p) => p.node_id) || []}
                affectedNodes={results?.affected_nodes} candidateRegion={results?.candidate_region}
                flowMetrics={results?.flow_metrics} selectedNodeId={selectedNode} onSelectNode={handleMapNode}
                picking={picking} onCancelPicking={() => setPicking(false)} highlightNode={leakNode} />
              <div className="absolute top-3 right-3 z-30 flex gap-2">
                <button onClick={() => setLeftOpen(!leftOpen)} aria-label={leftOpen ? 'Hide scenario panel' : 'Show scenario panel'} title={leftOpen ? 'Hide scenario panel' : 'Show scenario panel'}
                  className="w-9 h-9 rounded-lg border border-line bg-panel hover:bg-panel2 flex items-center justify-center">
                  {leftOpen ? <PanelLeftClose size={17} /> : <PanelLeftOpen size={17} />}
                </button>
                <button onClick={() => setRightOpen(!rightOpen)} aria-label={rightOpen ? 'Hide results panel' : 'Show results panel'} title={rightOpen ? 'Hide results panel' : 'Show results panel'}
                  className="w-9 h-9 rounded-lg border border-line bg-panel hover:bg-panel2 flex items-center justify-center">
                  {rightOpen ? <PanelRightClose size={17} /> : <PanelRightOpen size={17} />}
                </button>
              </div>
            </section>

            <aside className={`min-h-0 overflow-y-auto rounded-2xl border border-line bg-panel p-4 ${rightOpen ? '' : 'hidden'}`} aria-live="polite">
              <RightPanel {...{ results, running, examples, selectedNode, nodeSignal }} onRun={run} onSelectNode={(id) => setSelectedNode(id)} />
            </aside>
          </div>

          ) : (
          <div className="flex flex-col gap-4 p-4">
            <div className="rounded-2xl border border-line bg-panel p-4">
              <ScenarioPicker {...{ networks, network, scenarios, category, selectedId: scenarioId, leakNode, picking, useMeters, running, splitFilter }}
                onNetwork={setNetwork} onCategory={setCategory} onSelect={setScenarioId} onRun={run}
                onLeakNode={setLeakNode} onPicking={setPicking} onUseMeters={setUseMeters} onSplitFilter={setSplitFilter} />
            </div>
            <div className="h-[60vh]">
              <NetworkMap network={network} predictedLeaks={results?.predicted_leaks.map((p) => p.node_id) || []}
                affectedNodes={results?.affected_nodes} candidateRegion={results?.candidate_region}
                flowMetrics={results?.flow_metrics} selectedNodeId={selectedNode} onSelectNode={handleMapNode}
                picking={picking} onCancelPicking={() => setPicking(false)} highlightNode={leakNode} />
            </div>
            <div className="rounded-2xl border border-line bg-panel p-4">
              <RightPanel {...{ results, running, examples, selectedNode, nodeSignal }} onRun={run} onSelectNode={(id) => setSelectedNode(id)} />
            </div>
          </div>
          )}
        </main>
      )}
    </div>
  );
}

function RightPanel({ results, running, examples, selectedNode, nodeSignal, onRun, onSelectNode }: {
  results: Analysis | null; running: boolean; examples: { label: string; hint: string; s: Scenario }[];
  selectedNode: string | null; nodeSignal: number; onRun: (id?: string) => void; onSelectNode: (id: string) => void;
}) {
  if (running && !results) return <p className="text-[14px] text-muted p-2">Analysing the network…</p>;
  if (results) return <ResultView results={results} selectedNodeId={selectedNode} onSelectNode={onSelectNode} openNodeSignal={nodeSignal} />;
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-bold text-ink">Welcome</h2>
        <p className="text-[14px] text-muted mt-1">This tool finds where a water network is leaking, and tells a leak apart from normal changes such as higher demand or a pump stopping.</p>
      </div>
      <ol className="space-y-2 text-[14px] text-ink">
        <li className="flex gap-3"><span className="w-6 h-6 rounded-full bg-accentsoft text-accent text-xs font-bold flex items-center justify-center shrink-0">1</span>Pick a situation on the left.</li>
        <li className="flex gap-3"><span className="w-6 h-6 rounded-full bg-accentsoft text-accent text-xs font-bold flex items-center justify-center shrink-0">2</span>Press <strong>Analyse</strong>.</li>
        <li className="flex gap-3"><span className="w-6 h-6 rounded-full bg-accentsoft text-accent text-xs font-bold flex items-center justify-center shrink-0">3</span>Read the verdict here and see it on the map.</li>
      </ol>
      <div>
        <h3 className="text-[14px] font-semibold text-ink mb-2">Or try an example <span className="font-normal text-muted">(unseen test scenarios)</span></h3>
        <div className="space-y-2">
          {examples.map((e) => (
            <button key={e.s.id} onClick={() => onRun(e.s.id)}
              className="w-full flex items-center justify-between gap-3 rounded-xl border border-line bg-panel hover:bg-panel2 px-3 py-3 text-left">
              <span><span className="block text-[14px] font-semibold text-ink">{e.label}</span><span className="block text-[12px] text-muted">{e.hint}</span></span>
              <Play size={16} className="text-accent shrink-0" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
