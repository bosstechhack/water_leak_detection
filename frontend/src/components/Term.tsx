"use client";

import React, { useId, useState } from 'react';
import { GLOSSARY } from '@/lib/glossary';

/** A word with a dotted underline that explains itself on hover, focus or tap. */
export default function Term({ id, children }: { id: keyof typeof GLOSSARY | string; children?: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const tipId = useId();
  const entry = GLOSSARY[id as string];
  if (!entry) return <>{children}</>;
  return (
    <span className="relative inline-block">
      <button
        type="button"
        aria-describedby={open ? tipId : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((o) => !o)}
        className="underline decoration-dotted decoration-muted underline-offset-4 cursor-help text-inherit"
      >
        {children ?? entry.label}
      </button>
      {open && (
        <span
          id={tipId}
          role="tooltip"
          className="absolute z-50 left-0 top-full mt-2 w-64 rounded-lg border border-line bg-panel text-ink text-[13px] leading-snug p-3 shadow-xl font-normal"
        >
          <strong className="block mb-1">{entry.label}</strong>
          {entry.text}
        </span>
      )}
    </span>
  );
}
