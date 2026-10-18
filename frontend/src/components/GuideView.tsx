"use client";

import React from 'react';
import { CATEGORIES, GLOSSARY } from '@/lib/glossary';

const STEPS = [
  ['Simulate', 'A computer model of the water network is run for 24 hours: once on a normal day, and once for each situation we want to test.'],
  ['Compare', 'The system compares each situation with the normal day, node by node and pipe by pipe, and ignores differences that are only sensor noise.'],
  ['Follow the water', 'Every node receives exactly what its customers use. If water leaves a node and no customer meter accounts for it, that water is leaking.'],
  ['Decide the cause', 'A model looks at 14 summary numbers and decides: leak, demand change, pump or reservoir problem, tank change, blocked pipe, ageing, or normal.'],
  ['Rank the nodes', 'For a leak, every node gets a score. The highest score is the prediction (Top-1). The next ones are where to look if the first is wrong.'],
];

export default function GuideView() {
  return (
    <div className="max-w-4xl mx-auto p-5 sm:p-8 space-y-8 text-ink">
      <header>
        <h2 className="text-2xl font-bold">How to read this dashboard</h2>
        <p className="text-[14px] text-muted mt-1">Everything here is a simulation: we know the true answer, so we can check the system against it.</p>
      </header>

      <section>
        <h3 className="text-lg font-semibold mb-3">How it works in five steps</h3>
        <ol className="space-y-3">
          {STEPS.map(([t, d], i) => (
            <li key={t} className="flex gap-3 rounded-xl border border-line bg-panel p-4">
              <span className="w-8 h-8 rounded-full bg-accent text-accentink font-bold flex items-center justify-center shrink-0">{i + 1}</span>
              <div><p className="font-semibold">{t}</p><p className="text-[14px] text-muted">{d}</p></div>
            </li>
          ))}
        </ol>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-3">Using the Investigate tab</h3>
        <ul className="space-y-2 text-[14px] list-disc pl-5">
          <li><strong>1. Choose a network.</strong> Net1 is small, Net2 is medium, Net3 is the large benchmark.</li>
          <li><strong>2. Choose what happened.</strong> Leak, demand change, pump, tank, blockage, ageing, or a normal day.</li>
          <li><strong>3. Narrow it down.</strong> For leaks, type a node number or press <em>Pick on map</em>, then choose the size and conditions. Press <em>Surprise me</em> for a random one.</li>
          <li><strong>Analyse.</strong> Read the verdict, the reasons, and the order in which to inspect nodes. Click any node on the map to see its pressure over the day.</li>
        </ul>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-3">The kinds of situation</h3>
        <div className="grid sm:grid-cols-2 gap-3">
          {CATEGORIES.map((c) => (
            <div key={c.id} className="rounded-xl border border-line bg-panel p-4">
              <p className="font-semibold">{c.label}</p>
              <p className="text-[14px] text-muted">{c.blurb}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-3">Words used on screen</h3>
        <dl className="space-y-3">
          {Object.values(GLOSSARY).map((g) => (
            <div key={g.label} className="rounded-xl border border-line bg-panel p-4">
              <dt className="font-semibold">{g.label}</dt>
              <dd className="text-[14px] text-muted">{g.text}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-3">Training scenarios and test scenarios</h3>
        <div className="rounded-xl border border-line bg-panel p-4 space-y-2 text-[14px]">
          <p>About <strong>80% of scenarios are for learning</strong> (the system sets its noise levels and trains its cause model on them) and about <strong>20% are kept aside for testing</strong>.</p>
          <p className="text-muted">If the system were tested on scenarios it had learned from, it would look perfect and tell us nothing. Each scenario in the picker has a tag: <strong>Unseen test</strong> means the system never saw it, so its answer is an honest check; <strong>Training</strong> means it was part of learning.</p>
          <p className="text-muted">Near-copies stay together: all leaks at one node, and a scenario with its noisy twin, are on the same side of the split.</p>
        </div>
      </section>

      <section>
        <h3 className="text-lg font-semibold mb-2">Limits you should know</h3>
        <ul className="space-y-2 text-[14px] list-disc pl-5 text-muted">
          <li>The results are from simulation. Real networks add noise and surprises the simulation does not have.</li>
          <li>Telling a leak from a demand change needs smart meters at the nodes. Untick that option to see what happens without them.</li>
          <li>Very small leaks stay hidden in sensor noise and are reported as normal.</li>
        </ul>
      </section>
    </div>
  );
}
