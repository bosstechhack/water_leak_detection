"use client";

import React, { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, MapPin, Play, Search, Shuffle, X } from 'lucide-react';
import { CATEGORIES } from '@/lib/glossary';
import { NetworkInfo, Scenario } from '@/lib/types';
import Term from '@/components/Term';

interface Props {
  networks: NetworkInfo[];
  network: string;
  onNetwork: (id: string) => void;
  scenarios: Scenario[];
  category: string;
  onCategory: (id: string) => void;
  selectedId: string;
  onSelect: (id: string) => void;
  onRun: (id?: string) => void;
  running: boolean;
  leakNode: string;
  onLeakNode: (node: string) => void;
  picking: boolean;
  onPicking: (on: boolean) => void;
  useMeters: boolean;
  onUseMeters: (on: boolean) => void;
  splitFilter: 'test' | 'train' | 'all';
  onSplitFilter: (s: 'test' | 'train' | 'all') => void;
}

const SIZES = ['Tiny', 'Small', 'Medium', 'Large', 'Burst'];
const SIZE_HINT: Record<string, string> = {
  Tiny: 'Almost invisible', Small: 'Slow drip', Medium: 'Typical crack', Large: 'Serious leak', Burst: 'Pipe burst',
};
const CONDITIONS = [
  { id: 'any', label: 'Any' },
  { id: 'plain', label: 'Clean data' },
  { id: 'noisy', label: 'Noisy sensors' },
  { id: 'hidden', label: 'Hidden behind another event' },
  { id: 'later', label: 'Starts at another time' },
];
const HIDDEN_LABEL: Record<string, string> = {
  demand: 'a demand surge', source: 'a pump change', blockage: 'a blocked pipe', tank: 'a tank change', ageing: 'ageing',
};

export function friendlyTitle(s: Scenario): string {
  const p = s.params;
  if (p.category === 'leak' && p.node) return `Leak at node ${p.node}`;
  return s.name;
}

export function friendlySubtitle(s: Scenario): string {
  const p = s.params;
  if (p.category !== 'leak') return '';
  const parts = [`${p.size_label} leak (${p.size} m²)`, `from ${p.start_hour ?? 12}:00`];
  if (p.noisy) parts.push('noisy sensors');
  if (p.hidden_by) parts.push(`hidden behind ${HIDDEN_LABEL[p.hidden_by] || p.hidden_by}`);
  return parts.join(' · ');
}

function Chip({ active, onClick, children, title }: { active: boolean; onClick: () => void; children: React.ReactNode; title?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-pressed={active}
      className={`px-3 h-9 rounded-full border text-[13px] font-medium whitespace-nowrap transition-colors ${
        active ? 'bg-accent text-accentink border-accent' : 'bg-panel text-ink border-line hover:bg-panel2'
      }`}
    >
      {children}
    </button>
  );
}

function StepTitle({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <h3 className="flex items-center gap-2 text-[15px] font-semibold text-ink mb-2">
      <span className="w-6 h-6 rounded-full bg-accentsoft text-accent text-xs font-bold flex items-center justify-center">{n}</span>
      {children}
    </h3>
  );
}

export default function ScenarioPicker(p: Props) {
  const [size, setSize] = useState('any');
  const [condition, setCondition] = useState('any');
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(6);

  const visible = useMemo(
    () => p.scenarios.filter((s) => p.splitFilter === 'all' || s.params.split === p.splitFilter || s.params.split === 'reference'),
    [p.scenarios, p.splitFilter]);

  const countByCategory = useMemo(() => {
    const out: Record<string, number> = {};
    visible.forEach((s) => { out[s.params.category] = (out[s.params.category] || 0) + 1; });
    return out;
  }, [visible]);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    return visible.filter((s) => {
      if (s.params.category !== p.category) return false;
      if (p.category === 'leak') {
        if (p.leakNode && s.params.node !== p.leakNode) return false;
        if (size !== 'any' && s.params.size_label !== size) return false;
        const plain = !s.params.noisy && !s.params.hidden_by && (s.params.start_hour ?? 12) === 12;
        if (condition === 'plain' && !plain) return false;
        if (condition === 'noisy' && !s.params.noisy) return false;
        if (condition === 'hidden' && !s.params.hidden_by) return false;
        if (condition === 'later' && (s.params.start_hour ?? 12) === 12) return false;
      } else if (q && !(`${s.name} ${s.id}`.toLowerCase().includes(q))) {
        return false;
      }
      return true;
    });
  }, [visible, p.category, p.leakNode, size, condition, query]);

  const selected = p.scenarios.find((s) => s.id === p.selectedId);

  // Keep a valid choice selected: when filters change, jump to the first match
  const { onSelect, selectedId } = p;
  useEffect(() => {
    if (matches.length && !matches.some((s) => s.id === selectedId)) onSelect(matches[0].id);
  }, [matches, selectedId, onSelect]);
  const idx = matches.findIndex((s) => s.id === p.selectedId);
  const category = CATEGORIES.find((c) => c.id === p.category);

  const step = (d: number) => {
    if (!matches.length) return;
    const next = matches[(Math.max(idx, 0) + d + matches.length) % matches.length];
    p.onSelect(next.id);
  };

  const surprise = () => {
    const pool = visible.filter((s) => s.params.category === p.category);
    if (pool.length) p.onRun(pool[Math.floor(Math.random() * pool.length)].id);
  };

  const resetFilters = () => { setSize('any'); setCondition('any'); setQuery(''); p.onLeakNode(''); };

  return (
    <div className="space-y-6">
      {/* Which scenarios: unseen test vs training */}
      <section aria-label="Which scenarios to show">
        <h3 className="text-[15px] font-semibold text-ink mb-1">Which scenarios?</h3>
        <div className="grid grid-cols-3 gap-1 p-1 rounded-xl bg-panel2" role="radiogroup" aria-label="Scenario set">
          {([['test', 'Unseen test'], ['train', 'Training'], ['all', 'All']] as const).map(([id, label]) => (
            <button key={id} role="radio" aria-checked={p.splitFilter === id} onClick={() => p.onSplitFilter(id)}
              className={`h-9 rounded-lg text-[13px] font-semibold ${p.splitFilter === id ? 'bg-panel text-ink shadow' : 'text-muted hover:text-ink'}`}>
              {label}
            </button>
          ))}
        </div>
        <p className="text-[12px] text-muted mt-1.5 leading-snug">
          {p.splitFilter === 'test' && 'About 20% of scenarios were kept aside. The system never saw them, so results here are honest.'}
          {p.splitFilter === 'train' && 'The other 80%. The system learned from these, so it usually gets them right. Not a fair test.'}
          {p.splitFilter === 'all' && 'Both sets. Look for the "Unseen test" tag to know which is which.'}
        </p>
      </section>

      {/* Step 1: network */}
      <section aria-labelledby="step1">
        <StepTitle n={1}><span id="step1">Choose a water network</span></StepTitle>
        <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label="Water network">
          {(p.networks.length ? p.networks : [{ id: 'net3', name: 'Net3', junctions: 92, scenarios: 0 }]).map((n) => (
            <button
              key={n.id}
              role="radio"
              aria-checked={p.network === n.id}
              onClick={() => p.onNetwork(n.id)}
              className={`rounded-xl border p-3 text-left transition-colors ${
                p.network === n.id ? 'border-accent bg-accentsoft' : 'border-line bg-panel hover:bg-panel2'
              }`}
            >
              <span className="block text-sm font-bold text-ink uppercase">{n.id}</span>
              <span className="block text-[12px] text-muted leading-tight mt-0.5">{n.junctions} junctions</span>
            </button>
          ))}
        </div>
      </section>

      {/* Step 2: what happened */}
      <section aria-labelledby="step2">
        <StepTitle n={2}><span id="step2">What happened in the network?</span></StepTitle>
        <div className="grid grid-cols-2 gap-2">
          {CATEGORIES.map((c) => (
            <button
              key={c.id}
              onClick={() => { p.onCategory(c.id); resetFilters(); setLimit(6); }}
              aria-pressed={p.category === c.id}
              disabled={!countByCategory[c.id]}
              className={`rounded-xl border p-3 text-left transition-colors disabled:opacity-40 ${
                p.category === c.id ? 'border-accent bg-accentsoft' : 'border-line bg-panel hover:bg-panel2'
              }`}
            >
              <span className="flex items-center justify-between text-sm font-semibold text-ink">
                {c.label}
                <span className="text-[11px] text-muted font-normal">{countByCategory[c.id] || 0}</span>
              </span>
              <span className="block text-[12px] text-muted leading-snug mt-0.5">{c.blurb}</span>
            </button>
          ))}
        </div>
      </section>

      {/* Step 3: details */}
      <section aria-labelledby="step3">
        <StepTitle n={3}><span id="step3">Narrow it down</span></StepTitle>

        {p.category === 'leak' ? (
          <div className="space-y-4">
            <div>
              <label className="block text-[13px] font-medium text-ink mb-1" htmlFor="leaknode">Where is the leak?</label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                  <input
                    id="leaknode"
                    value={p.leakNode}
                    onChange={(e) => p.onLeakNode(e.target.value.trim())}
                    placeholder="Type a node number, e.g. 115"
                    inputMode="numeric"
                    className="w-full h-11 pl-9 pr-9 rounded-lg border border-line bg-panel text-ink placeholder:text-muted text-[14px]"
                  />
                  {p.leakNode && (
                    <button onClick={() => p.onLeakNode('')} aria-label="Clear location" className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-muted hover:text-ink">
                      <X size={16} />
                    </button>
                  )}
                </div>
                <button
                  onClick={() => p.onPicking(!p.picking)}
                  aria-pressed={p.picking}
                  className={`h-11 px-3 rounded-lg border text-[13px] font-medium flex items-center gap-1.5 ${
                    p.picking ? 'bg-accent text-accentink border-accent' : 'bg-panel text-ink border-line hover:bg-panel2'
                  }`}
                >
                  <MapPin size={16} /> {p.picking ? 'Click the map…' : 'Pick on map'}
                </button>
              </div>
              <p className="text-[12px] text-muted mt-1">Leave empty to browse leaks at any node.</p>
            </div>

            <div>
              <span className="block text-[13px] font-medium text-ink mb-1">How big is the leak?</span>
              <div className="flex flex-wrap gap-2">
                <Chip active={size === 'any'} onClick={() => setSize('any')}>Any size</Chip>
                {SIZES.map((s) => (
                  <Chip key={s} active={size === s} onClick={() => setSize(s)} title={SIZE_HINT[s]}>{s}</Chip>
                ))}
              </div>
            </div>

            <div>
              <span className="block text-[13px] font-medium text-ink mb-1">Conditions</span>
              <div className="flex flex-wrap gap-2">
                {CONDITIONS.map((c) => (
                  <Chip key={c.id} active={condition === c.id} onClick={() => setCondition(c.id)}>{c.label}</Chip>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div>
            <label className="block text-[13px] font-medium text-ink mb-1" htmlFor="scsearch">Search {category?.label.toLowerCase()} scenarios</label>
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <input
                id="scsearch"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. pump, 30%, noisy"
                className="w-full h-11 pl-9 pr-3 rounded-lg border border-line bg-panel text-ink placeholder:text-muted text-[14px]"
              />
            </div>
          </div>
        )}

        {/* Matches */}
        <div className="mt-4" aria-live="polite">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[13px] font-medium text-ink">
              {matches.length} matching scenario{matches.length === 1 ? '' : 's'}
            </span>
            <div className="flex items-center gap-1">
              <button onClick={() => step(-1)} aria-label="Previous scenario" className="w-8 h-8 rounded-lg border border-line bg-panel hover:bg-panel2 flex items-center justify-center"><ChevronLeft size={16} /></button>
              <button onClick={() => step(1)} aria-label="Next scenario" className="w-8 h-8 rounded-lg border border-line bg-panel hover:bg-panel2 flex items-center justify-center"><ChevronRight size={16} /></button>
              <button onClick={surprise} title="Run a random scenario of this kind" className="h-8 px-2.5 rounded-lg border border-line bg-panel hover:bg-panel2 text-[12px] font-medium flex items-center gap-1.5"><Shuffle size={14} /> Surprise me</button>
            </div>
          </div>

          {matches.length === 0 ? (
            <p className="text-[13px] text-muted rounded-lg border border-dashed border-line p-3">
              No scenario matches. {p.category === 'leak' && p.leakNode ? `Node ${p.leakNode} may not be a junction in this network; ` : ''}try clearing a filter.
              <button onClick={() => { setSize('any'); setCondition('any'); p.onLeakNode(''); setQuery(''); }} className="ml-1 text-accent font-medium underline">Clear filters</button>
            </p>
          ) : (
            <ul className="space-y-2" role="radiogroup" aria-label="Matching scenarios">
              {matches.slice(0, limit).map((s) => {
                const active = s.id === p.selectedId;
                return (
                  <li key={s.id}>
                    <button
                      role="radio"
                      aria-checked={active}
                      onClick={() => p.onSelect(s.id)}
                      className={`w-full text-left rounded-xl border p-3 transition-colors ${active ? 'border-accent bg-accentsoft' : 'border-line bg-panel hover:bg-panel2'}`}
                    >
                      <span className="flex items-start justify-between gap-2">
                        <span className="block text-[14px] font-semibold text-ink">{friendlyTitle(s)}</span>
                        <span className={`shrink-0 text-[11px] font-semibold px-2 py-0.5 rounded-full ${s.params.split === 'test' ? 'bg-oksoft text-ok' : 'bg-panel2 text-muted'}`}>
                          {s.params.split === 'test' ? 'Unseen test' : s.params.split === 'train' ? 'Training' : 'Reference'}
                        </span>
                      </span>
                      {friendlySubtitle(s) && <span className="block text-[12px] text-muted mt-0.5">{friendlySubtitle(s)}</span>}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          {matches.length > limit && (
            <button onClick={() => setLimit(limit + 8)} className="mt-2 text-[13px] text-accent font-medium underline">
              Show {Math.min(8, matches.length - limit)} more
            </button>
          )}
        </div>
      </section>

      {/* Options and run */}
      <section className="space-y-3">
        <label className="flex items-start gap-2 text-[13px] text-ink cursor-pointer">
          <input type="checkbox" className="mt-1 w-4 h-4" checked={p.useMeters} onChange={(e) => p.onUseMeters(e.target.checked)} />
          <span>Customers have smart <Term id="meters">demand meters</Term> at every node</span>
        </label>

        <button
          onClick={() => p.onRun()}
          disabled={p.running || !selected}
          className="w-full h-12 rounded-xl bg-accent text-accentink font-semibold text-[15px] flex items-center justify-center gap-2 hover:opacity-90 disabled:opacity-50"
        >
          {p.running ? <span className="w-5 h-5 border-2 border-accentink/40 border-t-accentink rounded-full animate-spin" /> : <Play size={18} />}
          {p.running ? 'Analysing…' : selected ? 'Analyse this scenario' : 'Choose a scenario first'}
        </button>
        {selected && (
          <p className="text-[12px] text-muted">
            Selected: <span className="font-medium text-ink">{friendlyTitle(selected)}</span>
            {friendlySubtitle(selected) ? ` (${friendlySubtitle(selected)})` : ''}
          </p>
        )}
      </section>
    </div>
  );
}
