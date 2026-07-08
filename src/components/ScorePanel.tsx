"use client";

import type { QualityScores } from "@/lib/types";

function barColor(v: number, invert = false) {
  const good = invert ? v <= 15 : v >= 70;
  const mid = invert ? v <= 40 : v >= 50;
  if (good) return "bg-emerald-500";
  if (mid) return "bg-amber-500";
  return "bg-rose-500";
}

function Row({
  label,
  value,
  invert,
}: {
  label: string;
  value: number;
  invert?: boolean;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-28 shrink-0 text-xs font-medium text-slate-500">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full ${barColor(value, invert)}`}
          style={{ width: `${Math.max(4, value)}%` }}
        />
      </div>
      <span className="w-9 shrink-0 text-right text-xs font-semibold tabular-nums text-slate-600">
        {value}
      </span>
    </div>
  );
}

export function ScorePanel({ scores }: { scores: QualityScores }) {
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-semibold text-brand-ink">Quality score</span>
        <span className="text-2xl font-black text-brand-ink">
          {scores.overall}
          <span className="text-sm font-medium text-slate-400">/100</span>
        </span>
      </div>
      <Row label="Educational" value={scores.educational} />
      <Row label="Trust" value={scores.trust} />
      <Row label="Actionable" value={scores.actionable} />
      <Row label="Authentic" value={scores.authentic} />
      <Row label="Human" value={scores.human} />
      <Row label="Promotional" value={scores.promotional} invert />
    </div>
  );
}
