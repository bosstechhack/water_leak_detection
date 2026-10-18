"use client";

import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Droplets, Lightbulb, Wrench, XCircle } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { Analysis, NodeMetric } from '@/lib/types';
import { CAUSE_ADVICE } from '@/lib/glossary';
import Term from '@/components/Term';

const FEATURE_LABELS: Record<string, string> = {
  drop_ratio: 'Biggest pressure drop (× noise level)',
  frac_hit: 'Share of junctions that lost pressure',
  median_ratio: 'Typical junction pressure drop (× noise)',
  conc_drop: 'Drop concentrated at one node',
  rise_ratio: 'Biggest pressure rise (× noise)',
  frac_rise: 'Share of junctions that gained pressure',
  flow_frac: 'Share of pipes with changed flow',
  source_change: 'Reservoir supply change (÷ total demand)',
  tank_change: 'Tank flow change (÷ total demand)',
  pump_drop: 'Pump flow lost (1 = pump off)',
  unacc_ratio: 'Unaccounted flow (× noise level)',
  unacc_conc: 'Unaccounted flow concentrated at one node',
  demand_frac: 'Share of nodes with changed customer use',
  demand_total: 'Total change in customer use (÷ demand)',
};

const CLASS_NAMES: Record<string, string> = {
  normal: 'Normal', leak: 'Leak', demand_change: 'Demand change', source_event: 'Pump / reservoir',
  tank_event: 'Tank change', valve_block: 'Blocked pipe', ageing: 'Pipe ageing',
};

const LPS = (m3s: number) => (m3s * 1000).toFixed(m3s * 1000 < 10 ? 2 : 1);

function confidenceLabel(p: number) {
  if (p >= 0.85) return { text: 'High confidence', tone: 'ok' as const };
  if (p >= 0.6) return { text: 'Medium confidence', tone: 'warn' as const };
  return { text: 'Low confidence', tone: 'danger' as const };
}

function Tone({ tone, children }: { tone: 'ok' | 'warn' | 'danger' | 'accent'; children: React.ReactNode }) {
  const cls = {
    ok: 'bg-oksoft text-ok', warn: 'bg-warnsoft text-warn', danger: 'bg-dangersoft text-danger', accent: 'bg-accentsoft text-accent',
  }[tone];
  return <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[12px] font-semibold ${cls}`}>{children}</span>;
}

function Card({ title, icon, children }: { title?: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-line bg-panel p-4">
      {title && <h3 className="flex items-center gap-2 text-[15px] font-semibold text-ink mb-2">{icon}{title}</h3>}
      {children}
    </section>
  );
}

/** One sentence per signal, in plain language. */
function buildEvidence(r: Analysis): string[] {
  const f = r.features;
  const out: string[] = [];
  if (f.frac_hit > 0) {
    out.push(`${Math.round(f.frac_hit * 100)}% of the junctions lost more pressure than normal sensor noise explains. The biggest drop is ${r.max_pressure_drop.toFixed(1)} m${r.worst_node ? ` at node ${r.worst_node}` : ''}.`);
  } else {
    out.push('No junction lost more pressure than normal sensor noise explains.');
  }
  if (f.unacc_ratio >= 1) {
    const top = Object.values(r.node_metrics).sort((a, b) => b.flow_divergence - a.flow_divergence)[0];
    out.push(`Water is disappearing${top ? ` at node ${top.node_id}` : ''}: about ${top ? LPS(top.flow_divergence) : '?'} litres per second leave the pipes with no customer meter recording it. Only a leak does that.`);
  } else if (f.demand_frac > 0) {
    out.push(`Customer meters recorded a change in water use at ${Math.round(f.demand_frac * 100)}% of nodes, which explains the extra flow. So it is not a leak.`);
  } else {
    out.push('Every litre of water is accounted for by customer meters, so no water is being lost.');
  }
  if (f.pump_drop > 0.5) out.push(`A pump lost ${Math.round(f.pump_drop * 100)}% of its flow.`);
  if (f.source_change > 0.2) out.push(`Supply from the reservoirs changed by ${Math.round(f.source_change * 100)}% of total customer demand.`);
  if (f.tank_change > 0.2) out.push(`The storage tanks are supplying or absorbing ${Math.round(f.tank_change * 100)}% of total demand more than usual.`);
  if (f.frac_rise > 0.05) out.push('Some junctions gained pressure while others lost it. That pattern is typical of a blocked pipe or a tank change, not a leak.');
  if (f.frac_hit > 0.5 && f.unacc_ratio < 1) out.push('The pressure loss is spread over most of the network instead of centred on one place.');
  return out;
}

export function NodeInspector({ metric, isLeak }: { metric?: NodeMetric; isLeak: boolean }) {
  if (!metric) {
    return <p className="text-[14px] text-muted">Run an analysis, then click a node on the map to see its pressure over the day.</p>;
  }
  const data = metric.baseline_series.map((v, i) => ({ hour: i, normal: v, now: metric.current_series[i] }));
  const status = isLeak ? { text: 'Probable leak', tone: 'danger' as const }
    : metric.status === 'Pressure drop' ? { text: 'Lost pressure', tone: 'warn' as const } : { text: 'Looks normal', tone: 'ok' as const };
  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-lg font-bold text-ink">Node {metric.node_id}</h3>
          <p className="text-[13px] text-muted">{metric.node_type} · {metric.elevation.toFixed(1)} m above datum</p>
        </div>
        <Tone tone={status.tone}>{status.text}</Tone>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-xl bg-panel2 p-3">
          <p className="text-[12px] text-muted"><Term id="pressure">Pressure</Term> now</p>
          <p className="text-xl font-bold text-ink">{metric.current_pressure.toFixed(1)} <span className="text-sm font-normal text-muted">m</span></p>
          <p className="text-[12px] text-muted">normal {metric.baseline_pressure.toFixed(1)} m · worst drop {metric.pressure_drop.toFixed(2)} m</p>
        </div>
        <div className="rounded-xl bg-panel2 p-3">
          <p className="text-[12px] text-muted"><Term id="unaccounted">Unaccounted flow</Term></p>
          <p className={`text-xl font-bold ${metric.flow_divergence > 0.001 ? 'text-danger' : 'text-ink'}`}>{LPS(metric.flow_divergence)} <span className="text-sm font-normal text-muted">L/s</span></p>
          <p className="text-[12px] text-muted">{metric.flow_divergence > 0.001 ? 'water lost with no meter' : 'all water accounted for'}</p>
        </div>
      </div>
      <div>
        <p className="text-[13px] font-medium text-ink mb-1">Pressure over the day</p>
        <div className="h-44 rounded-xl border border-line bg-panel p-2">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 6, right: 8, left: -14, bottom: 0 }}>
              <XAxis dataKey="hour" stroke="var(--muted)" fontSize={11} tickFormatter={(h) => `${h}h`} />
              <YAxis stroke="var(--muted)" fontSize={11} domain={['auto', 'auto']} unit=" m" />
              <Tooltip contentStyle={{ background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 8, fontSize: 12, color: 'var(--ink)' }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="normal" name="Normal day" stroke="var(--accent)" strokeWidth={2.5} dot={false} />
              <Line type="monotone" dataKey="now" name="This scenario" stroke="var(--danger)" strokeWidth={2.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      <p className="text-[12px] text-muted">Pipes touching this node: {metric.connected_pipes.join(', ') || 'none'}.</p>
    </div>
  );
}

export default function ResultView({ results, selectedNodeId, onSelectNode, openNodeSignal }: {
  results: Analysis; selectedNodeId: string | null; onSelectNode: (id: string) => void; openNodeSignal: number;
}) {
  const [tab, setTab] = useState<'result' | 'node'>('result');
  useEffect(() => { if (openNodeSignal > 0) setTab('node'); }, [openNodeSignal]);
  useEffect(() => { setTab('result'); }, [results]);
  const [tech, setTech] = useState(false);
  const cls = results.event_class || (results.has_anomaly ? 'leak' : 'normal');
  const advice = CAUSE_ADVICE[cls] || CAUSE_ADVICE.normal;
  const topProb = results.probabilities ? Math.max(0, ...Object.values(results.probabilities)) : 0;
  const conf = confidenceLabel(topProb);
  const leaks = results.predicted_leaks;
  const evidence = useMemo(() => buildEvidence(results), [results]);
  const truth = results.scenario_truth;
  const causeOk = truth.event_class ? truth.event_class === cls : null;
  const topOk = truth.leak_nodes && leaks.length ? String(truth.leak_nodes).split(', ').includes(leaks[0].node_id) : null;
  const isLeak = cls === 'leak';
  const clear = leaks.length > 1 ? leaks[1].confidence_score / leaks[0].confidence_score < 0.5 : true;
  const tone = cls === 'normal' ? 'ok' : isLeak ? 'danger' : 'warn';
  const Icon = cls === 'normal' ? CheckCircle2 : AlertTriangle;
  const probs = Object.entries(results.probabilities || {}).sort((a, b) => b[1] - a[1]);
  const selMetric = selectedNodeId ? results.node_metrics[selectedNodeId] : undefined;

  return (
    <div className="space-y-4">
      <div role="tablist" className="grid grid-cols-2 gap-1 p-1 rounded-xl bg-panel2">
        {(['result', 'node'] as const).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
            className={`h-9 rounded-lg text-[13px] font-semibold ${tab === t ? 'bg-panel text-ink shadow' : 'text-muted hover:text-ink'}`}>
            {t === 'result' ? 'Verdict' : `Node ${selectedNodeId ?? ''}`.trim()}
          </button>
        ))}
      </div>

      {tab === 'node' ? (
        <Card><NodeInspector metric={selMetric} isLeak={leaks.some((l) => l.node_id === selectedNodeId)} /></Card>
      ) : (
        <>
          {/* Verdict */}
          <section className={`rounded-2xl border p-4 ${tone === 'ok' ? 'border-ok/40 bg-oksoft' : tone === 'danger' ? 'border-danger/40 bg-dangersoft' : 'border-warn/40 bg-warnsoft'}`}>
            <div className="flex items-start gap-3">
              <Icon size={30} className={tone === 'ok' ? 'text-ok' : tone === 'danger' ? 'text-danger' : 'text-warn'} />
              <div className="min-w-0">
                <h2 className="text-xl font-bold text-ink leading-tight">
                  {isLeak && leaks.length ? `Probable leak near node ${leaks[0].node_id}` : advice.title}
                </h2>
                <div className="mt-2 flex flex-wrap gap-2">
                  {results.split === 'test' && <Tone tone="ok">Unseen test scenario</Tone>}
                  {results.split === 'train' && <Tone tone="warn">Used in training</Tone>}
                  <Tone tone={conf.tone}>{conf.text} ({Math.round(topProb * 100)}%)</Tone>
                  {isLeak && leaks.length > 0 && <Tone tone={clear ? 'ok' : 'warn'}>{clear ? 'Clear first choice' : 'Close call between nodes'}</Tone>}
                </div>
              </div>
            </div>
            <div className="mt-3 flex items-start gap-2 rounded-xl bg-panel/70 p-3 text-[14px] text-ink">
              <Wrench size={18} className="mt-0.5 shrink-0 text-muted" />
              <p><strong>What to do: </strong>{advice.action}</p>
            </div>
          </section>

          {results.split === 'train' && (
            <p className="rounded-xl bg-warnsoft text-warn text-[13px] p-3">
              The system learned from this scenario, so a correct answer here proves little. Choose an <strong>Unseen test</strong> scenario for an honest check.
            </p>
          )}

          {/* Evidence */}
          <Card title="How do we know?" icon={<Lightbulb size={18} className="text-accent" />}>
            <ul className="space-y-2 text-[14px] text-ink">
              {evidence.map((e, i) => (
                <li key={i} className="flex gap-2"><span className="mt-2 w-1.5 h-1.5 rounded-full bg-accent shrink-0" />{e}</li>
              ))}
            </ul>
          </Card>

          {/* Candidates */}
          {isLeak && leaks.length > 0 && (
            <Card title="Where to look, in order" icon={<Droplets size={18} className="text-danger" />}>
              <ol className="space-y-2">
                {leaks.map((l, i) => {
                  const share = Math.max(6, Math.round((l.confidence_score / leaks[0].confidence_score) * 100));
                  return (
                    <li key={l.node_id}>
                      <button
                        onClick={() => { onSelectNode(l.node_id); setTab('node'); }}
                        className="w-full text-left rounded-xl border border-line bg-panel hover:bg-panel2 p-3"
                      >
                        <span className="flex items-center justify-between gap-2">
                          <span className="flex items-center gap-2">
                            <span className={`w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center ${i === 0 ? 'bg-danger text-white' : 'bg-panel2 text-ink border border-line'}`}>{i + 1}</span>
                            <span className="font-semibold text-ink">Node {l.node_id}</span>
                          </span>
                          <ChevronRight size={16} className="text-muted" />
                        </span>
                        <span className="block mt-2 h-2 rounded bg-panel2"><span className="block h-2 rounded bg-danger" style={{ width: `${share}%` }} /></span>
                        <span className="block mt-1 text-[12px] text-muted">
                          pressure dropped {l.pressure_drop.toFixed(2)} m · {LPS(l.flow_divergence)} L/s unaccounted
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ol>
              {results.candidate_region.length > 0 && (
                <p className="text-[13px] text-muted mt-3">
                  <Term id="region">Search region</Term> (top node and its pipe neighbours): <strong className="text-ink">{results.candidate_region.join(', ')}</strong>
                </p>
              )}
            </Card>
          )}

          {/* Answer key */}
          {truth.description && (
            <Card title="Check against the answer key">
              <p className="text-[13px] text-muted mb-2">Because this is a simulation, we know what really happened:</p>
              <p className="text-[14px] text-ink mb-3"><strong>{truth.description}</strong></p>
              <div className="flex flex-wrap gap-2">
                {causeOk !== null && (
                  <Tone tone={causeOk ? 'ok' : 'danger'}>
                    {causeOk ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                    {causeOk ? 'Cause is correct' : `Cause is wrong (it was: ${CLASS_NAMES[truth.event_class] || truth.event_class})`}
                  </Tone>
                )}
                {topOk !== null && (
                  <Tone tone={topOk ? 'ok' : 'danger'}>
                    {topOk ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                    {topOk ? 'Exact leak node found (Top-1)' : `Top-1 missed by ${results.localization_error_hops ?? '?'} pipe hops`}
                  </Tone>
                )}
              </div>
            </Card>
          )}

          {/* Technical */}
          <section className="rounded-2xl border border-line bg-panel">
            <button onClick={() => setTech(!tech)} aria-expanded={tech} className="w-full flex items-center justify-between px-4 py-3 text-[14px] font-semibold text-ink">
              Technical details
              {tech ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
            </button>
            {tech && (
              <div className="px-4 pb-4 space-y-4">
                <div>
                  <p className="text-[13px] font-medium text-ink mb-1">What the model thinks (<Term id="confidence" />)</p>
                  <div className="space-y-1.5">
                    {probs.slice(0, 5).map(([name, p]) => (
                      <div key={name} className="flex items-center gap-2 text-[12px]">
                        <span className="w-32 text-muted">{CLASS_NAMES[name] || name}</span>
                        <span className="flex-1 h-2 rounded bg-panel2"><span className="block h-2 rounded bg-accent" style={{ width: `${p * 100}%` }} /></span>
                        <span className="w-10 text-right font-mono text-ink">{(p * 100).toFixed(0)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-[13px] font-medium text-ink mb-1">The 14 numbers the model looks at</p>
                  <table className="w-full text-[12px]">
                    <tbody>
                      {Object.entries(results.features).map(([k, v]) => (
                        <tr key={k} className="border-t border-line">
                          <td className="py-1 pr-2 text-muted">{FEATURE_LABELS[k] || k}</td>
                          <td className="py-1 text-right font-mono text-ink">{Math.abs(v) >= 1000 ? v.toExponential(1) : v.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="text-[12px] text-muted">
                  Leak <Term id="score" /> = unaccounted flow (scaled 0–1) + 0.3 × pressure drop (scaled 0–1). The pressure noise level for this network is {results.detection.pressure_threshold_m?.toFixed(2)} m.
                </p>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
