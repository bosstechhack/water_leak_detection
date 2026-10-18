"use client";

import React, { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { fetchEvaluation } from '@/lib/api';
import Term from '@/components/Term';

/* eslint-disable @typescript-eslint/no-explicit-any */
const pct = (x?: number | null) => (x === undefined || x === null ? '-' : `${(x * 100).toFixed(1)}%`);
const NAMES: Record<string, string> = {
  normal: 'Normal', leak: 'Leak', demand_change: 'Demand change', source_event: 'Pump / reservoir',
  tank_event: 'Tank', valve_block: 'Blocked pipe', ageing: 'Pipe ageing',
};
const METHODS: Record<string, string> = {
  legacy_pressure_plus_divergence: 'First version (pressure + 50 × flow)',
  proposed: 'Final method (unaccounted flow + pressure)',
  proposed_with_graph_smoothing: 'Final method + neighbour smoothing',
  proposed_no_demand_meters: 'Final method without demand meters',
  pressure_only: 'Pressure only',
  pressure_only_with_graph_smoothing: 'Pressure only + neighbour smoothing',
};

function Big({ label, value, note, tone }: { label: React.ReactNode; value: string; note: string; tone?: 'ok' | 'danger' }) {
  return (
    <div className="rounded-2xl border border-line bg-panel p-4">
      <p className="text-[13px] text-muted">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${tone === 'ok' ? 'text-ok' : tone === 'danger' ? 'text-danger' : 'text-ink'}`}>{value}</p>
      <p className="text-[12px] text-muted mt-1">{note}</p>
    </div>
  );
}

function Table({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-line">
      <table className="w-full text-[13px]">
        <thead className="bg-panel2 text-muted">
          <tr>{head.map((h) => <th key={h} className="text-left px-3 py-2 font-semibold">{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-line text-ink">
              {r.map((c, j) => <td key={j} className={`px-3 py-2 ${j > 0 ? 'font-mono' : ''}`}>{c}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Section({ title, summary, children, open: initial = false }: { title: string; summary: string; children: React.ReactNode; open?: boolean }) {
  const [open, setOpen] = useState(initial);
  return (
    <section className="rounded-2xl border border-line bg-panel">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="w-full flex items-start justify-between gap-3 text-left px-4 py-3">
        <span>
          <span className="block text-[15px] font-semibold text-ink">{title}</span>
          <span className="block text-[13px] text-muted mt-0.5">{summary}</span>
        </span>
        {open ? <ChevronDown size={18} className="mt-1 shrink-0" /> : <ChevronRight size={18} className="mt-1 shrink-0" />}
      </button>
      {open && <div className="px-4 pb-4 space-y-3">{children}</div>}
    </section>
  );
}

export default function PerformanceView() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchEvaluation().then(setData).catch(() => setError('The results file is missing. Run ml_pipeline/evaluate.py, then reload this page.'));
  }, []);

  if (error) return <div className="p-8 text-warn text-[14px]">{error}</div>;
  if (!data) return <div className="p-8 text-muted text-[14px]">Loading results…</div>;

  const det = data.detection, loc = data.localization;
  const cls = data.classification.forest_with_demand_meters, clsNo = data.classification.forest_without_demand_meters;
  const labels: string[] = cls.labels;
  const sizes = (data.size_sensitivity || []).map((s: any) => ({
    size: `${s.area_m2} m²`, 'Noticed at all': +(s.detected * 100).toFixed(0), 'Exact node found': +(s.top1 * 100).toFixed(0),
  }));

  return (
    <div className="space-y-5 max-w-5xl mx-auto p-5 sm:p-8">
      <header>
        <h2 className="text-2xl font-bold text-ink">How well does it work?</h2>
        <p className="text-[14px] text-muted mt-1 max-w-3xl">
          We simulated {data.n_scenarios} situations on {Object.keys(data.networks).length} networks and split them: <strong className="text-ink">{data.split.n_train} for learning</strong> and{' '}
          <strong className="text-ink">{data.split.n_test} kept aside for testing</strong> (about 20%). Every number below is measured only on the test scenarios, which the system never saw while learning.
          These are simulation results, not real sensor data.
        </p>
        <p className="text-[12px] text-muted mt-1 max-w-3xl">
          Near-copies of a scenario (the same leak node at other sizes, or the same scenario with sensor noise) always stay on the same side of the split, so the test cannot be passed by memorising.
        </p>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <Big tone="ok" label={<>Leaks found at the <Term id="top1">exact node</Term></>} value={pct(loc.proposed.top1)} note={`First version: ${pct(loc.legacy_pressure_plus_divergence.top1)}`} />
        <Big label="Real leak in the first 5 nodes" value={pct(loc.proposed.top5)} note={`Average miss: ${loc.proposed.mean_hops.toFixed(2)} pipes`} />
        <Big tone="ok" label="False alarms on normal days" value={pct(det.classifier.false_alarm_rate)} note={`A fixed 0.5 m alarm: ${pct(det['legacy_fixed_0.5m'].false_alarm_rate)}`} />
        <Big label="Right cause identified" value={pct(cls.accuracy)} note={`on test scenarios. On training scenarios it was ${pct(cls.train_accuracy)}`} />
      </div>

      <Section open title="Does it find leaks?" summary={`Out of ${loc.proposed.n} unseen leaks, the exact node came first ${pct(loc.proposed.top1)} of the time, versus ${pct(loc.legacy_pressure_plus_divergence.top1)} for the first version.`}>
        <Table head={['Method', 'Leaks tested', 'Exact node (Top-1)', 'In first 3', 'In first 5', 'Average miss (pipes)']}
          rows={Object.entries(loc).map(([k, v]: any) => [METHODS[k] || k, v.n, pct(v.top1), pct(v.top3), pct(v.top5), v.mean_hops.toFixed(2)])} />
        <p className="text-[13px] text-muted">
          The final method looks for water that disappears without a customer meter noticing. Without meters it still works, but misses more. Smoothing over neighbouring nodes did not help, so it is not used. Only {loc.proposed.n} test leaks are scored, so one miss moves the percentage by about {(100 / loc.proposed.n).toFixed(1)} points.
        </p>
      </Section>

      <Section title="Does it notice small leaks?" summary="Large leaks are easy to notice. Tiny leaks hide in sensor noise. Only a few test leaks exist per size, so read this chart loosely.">
        <div className="h-60 rounded-xl border border-line bg-panel p-3">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={sizes}>
              <XAxis dataKey="size" stroke="var(--muted)" fontSize={12} />
              <YAxis stroke="var(--muted)" fontSize={12} unit="%" domain={[0, 100]} />
              <Tooltip contentStyle={{ background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 8, fontSize: 12, color: 'var(--ink)' }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="Noticed at all" fill="var(--accent)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Exact node found" fill="var(--danger)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="text-[13px] text-muted">The very biggest leak lowers pressure across the whole network, which makes its exact node hard to pinpoint.</p>
      </Section>

      <Section title="Can it tell a leak from other changes?" summary={`Right cause ${pct(cls.accuracy)} of the time on unseen scenarios (${pct(cls.train_accuracy)} on the ones it learned from). Leaks are recognised ${pct(det.leak_recall)} of the time, and only ${pct(det.leak_false_alarm_rate)} of non-leaks are wrongly called leaks.`}>
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full text-[13px]">
            <thead className="bg-panel2 text-muted">
              <tr><th className="px-3 py-2 text-left">What really happened ↓ / system said →</th>{labels.map((l) => <th key={l} className="px-2 py-2">{NAMES[l] || l}</th>)}<th className="px-2 py-2">Right</th></tr>
            </thead>
            <tbody>
              {cls.confusion.map((row: number[], i: number) => {
                const total = row.reduce((a, b) => a + b, 0) || 1;
                return (
                  <tr key={i} className="border-t border-line text-ink">
                    <td className="px-3 py-2 font-semibold">{NAMES[labels[i]] || labels[i]}</td>
                    {row.map((c, j) => (
                      <td key={j} className="px-2 py-2 text-center font-mono"
                        style={{ background: c ? `color-mix(in srgb, var(${i === j ? '--ok' : '--danger'}) ${Math.min(15 + (c / total) * 70, 80)}%, transparent)` : undefined }}>{c || ''}</td>
                    ))}
                    <td className="px-2 py-2 text-center font-mono">{pct(row[i] / total)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="text-[13px] text-muted">Green = correct, red = confused. Events too small to rise above sensor noise are reported as normal, which accounts for most of the red.</p>
      </Section>

      <Section title="Does it work on a network it has never seen?" summary="Train on two networks, test on the third network\u2019s test scenarios. Leaks mostly carry over; telling the other causes apart does not yet.">
        <Table head={['Unseen network', 'Overall right', 'Leaks recognised', 'Calls that were really leaks', 'Right without demand meters']}
          rows={Object.entries(cls.leave_one_network_out).map(([k, v]: any) => [k, pct(v.accuracy), pct(v.leak_recall), pct(v.leak_precision), pct(clsNo.leave_one_network_out[k]?.accuracy)])} />
      </Section>

      <Section title="Detailed numbers" summary="Per-scenario type, node type and detection method.">
        <Table head={['Method', 'Precision', 'Recall', 'F1', 'False alarms']}
          rows={[['legacy_fixed_0.5m', 'Fixed 0.5 m alarm'], ['adaptive_pressure', 'Learned pressure threshold'], ['classifier', 'Full system']].map(([k, n]) => [n, pct(det[k].precision), pct(det[k].recall), pct(det[k].f1), pct(det[k].false_alarm_rate)])} />
        <Table head={['Scenario group', 'Leaks', 'Exact node', 'In first 5', 'Average miss']}
          rows={Object.entries(data.localization_breakdown.by_group).map(([k, v]: any) => [k, v.n, pct(v.top1), pct(v.top5), v.mean_hops.toFixed(2)])} />
        <Table head={['Node type / network', 'Leaks', 'Exact node', 'In first 5', 'Average miss']}
          rows={[...Object.entries(data.localization_breakdown.by_node_type), ...Object.entries(data.localization_breakdown.by_network)].map(([k, v]: any) => [k, v.n, pct(v.top1), pct(v.top5), v.mean_hops.toFixed(2)])} />
      </Section>
    </div>
  );
}
