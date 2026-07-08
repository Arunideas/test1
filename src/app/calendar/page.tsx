"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { CalendarEntry, CalendarStatus } from "@/lib/types";

type Entry = CalendarEntry & { categoryName: string; contentTypeName: string };

interface Insights {
  config: { rotationWindowDays: number; duplicateThreshold: number };
  next: { topic: string; score: number; categoryId: string } | null;
  underrepresented: { categoryName: string; deficit: number; count: number }[];
  categoryBalance: { categoryName: string; count: number; target: number }[];
  trending: { topic: string; trendScore: number; categoryName: string }[];
  duplicateAlerts: { a: string; b: string; score: number }[];
}

const STATUS_STYLE: Record<CalendarStatus, string> = {
  planned: "bg-slate-100 text-slate-600 border-slate-200",
  approved: "bg-blue-50 text-blue-700 border-blue-200",
  generated: "bg-violet-50 text-violet-700 border-violet-200",
  published: "bg-emerald-50 text-emerald-700 border-emerald-200",
  rejected: "bg-rose-50 text-rose-600 border-rose-200",
  skipped: "bg-slate-50 text-slate-400 border-slate-200 line-through",
};

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function parseYmd(s: string): Date {
  return new Date(s + "T00:00:00Z");
}

export default function CalendarPage() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [insights, setInsights] = useState<Insights | null>(null);
  const [days, setDays] = useState(90);
  const [planning, setPlanning] = useState(false);
  const [summary, setSummary] = useState<null | {
    scheduled: number;
    uniqueTopics: number;
    duplicateTopics: number;
    categoriesUsed: number;
    maxSimilarity: number;
  }>(null);
  const [selected, setSelected] = useState<Entry | null>(null);
  const [dupText, setDupText] = useState("");
  const [dupResult, setDupResult] = useState<null | { posted: boolean; matches: { topic: string; score: number }[] }>(null);

  const loadCalendar = useCallback(async () => {
    const [c, i] = await Promise.all([
      fetch("/api/calendar").then((r) => r.json()),
      fetch("/api/insights").then((r) => r.json()),
    ]);
    setEntries(c.entries ?? []);
    setInsights(i);
  }, []);

  useEffect(() => {
    loadCalendar();
  }, [loadCalendar]);

  async function onPlan() {
    setPlanning(true);
    try {
      const res = await fetch("/api/calendar/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ days }),
      });
      const data = await res.json();
      setSummary(data.summary);
      await loadCalendar();
    } finally {
      setPlanning(false);
    }
  }

  async function patchEntry(id: string, patch: Partial<{ status: CalendarStatus; note: string }>) {
    const res = await fetch(`/api/calendar/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    const data = await res.json();
    if (data.entry) {
      setEntries((prev) => prev.map((e) => (e.id === id ? { ...e, ...data.entry } : e)));
      setSelected((s) => (s && s.id === id ? { ...s, ...data.entry } : s));
      loadCalendar();
    }
  }

  async function generateEntry(id: string) {
    const res = await fetch(`/api/calendar/${id}/generate`, { method: "POST" });
    const data = await res.json();
    if (data.entry) {
      setEntries((prev) => prev.map((e) => (e.id === id ? { ...e, ...data.entry } : e)));
      setSelected((s) => (s && s.id === id ? { ...s, ...data.entry } : s));
    }
  }

  async function runDupCheck() {
    if (!dupText.trim()) return;
    const res = await fetch("/api/duplicate-check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic: dupText.trim() }),
    });
    setDupResult(await res.json());
  }

  const weeks = useMemo(() => buildWeeks(entries), [entries]);
  const byDate = useMemo(() => {
    const m = new Map<string, Entry>();
    for (const e of entries) m.set(e.date, e);
    return m;
  }, [entries]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-brand-ink">Content Calendar</h1>
          <p className="text-sm text-slate-500">
            Plan months of content automatically — no duplicate topics, balanced categories.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs font-semibold text-slate-500">Days</label>
          <input
            type="number"
            min={7}
            max={365}
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="w-20 rounded-xl border border-slate-300 px-3 py-2 text-sm"
          />
          <button className="btn-primary" onClick={onPlan} disabled={planning}>
            {planning ? "Planning…" : `Plan ${days} days`}
          </button>
        </div>
      </div>

      {summary && (
        <div className="card flex flex-wrap items-center gap-x-6 gap-y-2 p-4 text-sm">
          <Stat label="Scheduled" value={summary.scheduled} />
          <Stat label="Unique topics" value={summary.uniqueTopics} />
          <Stat
            label="Duplicate topics"
            value={summary.duplicateTopics}
            good={summary.duplicateTopics === 0}
          />
          <Stat label="Categories used" value={summary.categoriesUsed} />
          <Stat label="Max similarity" value={summary.maxSimilarity} />
          {summary.duplicateTopics === 0 && (
            <span className="chip border-emerald-200 bg-emerald-50 text-emerald-700">
              ✓ No duplicate topics
            </span>
          )}
        </div>
      )}

      {/* Content intelligence */}
      {insights && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <IntelCard title="Which topic should be next?" accent="blue">
            {insights.next ? (
              <>
                <p className="text-sm font-semibold text-brand-ink">{insights.next.topic}</p>
                <p className="mt-1 text-xs text-slate-500">Score {insights.next.score}/100</p>
              </>
            ) : (
              <p className="text-sm text-slate-400">No topics available.</p>
            )}
          </IntelCard>

          <IntelCard title="Which category is underrepresented?" accent="amber">
            {insights.underrepresented.length ? (
              <ul className="space-y-1 text-xs text-slate-600">
                {insights.underrepresented.slice(0, 3).map((u) => (
                  <li key={u.categoryName} className="flex justify-between">
                    <span>{u.categoryName}</span>
                    <span className="text-amber-600">+{u.deficit}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-400">Well balanced.</p>
            )}
          </IntelCard>

          <IntelCard title="Which topics are trending?" accent="violet">
            <ul className="space-y-1 text-xs text-slate-600">
              {insights.trending.slice(0, 3).map((t) => (
                <li key={t.topic} className="flex items-start justify-between gap-2">
                  <span className="line-clamp-1">{t.topic}</span>
                  <span className="shrink-0 font-semibold text-violet-600">{t.trendScore}</span>
                </li>
              ))}
            </ul>
          </IntelCard>

          <IntelCard title="Have we posted this before?" accent="emerald">
            <div className="flex gap-1">
              <input
                className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-xs"
                placeholder="Type a topic…"
                value={dupText}
                onChange={(e) => setDupText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && runDupCheck()}
              />
              <button className="btn-ghost px-2 py-1.5 text-xs" onClick={runDupCheck}>
                Check
              </button>
            </div>
            {dupResult && (
              <div className="mt-2 text-xs">
                {dupResult.posted ? (
                  <p className="text-rose-600">
                    Likely duplicate ({Math.round((dupResult.matches[0]?.score ?? 0) * 100)}%): {dupResult.matches[0]?.topic}
                  </p>
                ) : (
                  <p className="text-emerald-600">
                    New — closest {Math.round((dupResult.matches[0]?.score ?? 0) * 100)}%
                  </p>
                )}
              </div>
            )}
          </IntelCard>
        </div>
      )}

      {insights && insights.duplicateAlerts.length > 0 && (
        <div className="card border-rose-200 bg-rose-50 p-4">
          <p className="text-sm font-semibold text-rose-700">
            {insights.duplicateAlerts.length} duplicate alert(s) in the calendar
          </p>
          <ul className="mt-1 space-y-0.5 text-xs text-rose-600">
            {insights.duplicateAlerts.slice(0, 3).map((a, i) => (
              <li key={i}>
                “{a.a}” ≈ “{a.b}” ({Math.round(a.score * 100)}%)
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Calendar grid */}
      {entries.length === 0 ? (
        <div className="card p-10 text-center text-sm text-slate-500">
          No calendar yet. Click <b>Plan {days} days</b> to generate a duplicate-free content
          calendar.
        </div>
      ) : (
        <div className="card overflow-x-auto p-4">
          <div className="grid min-w-[820px] grid-cols-7 gap-2">
            {WEEKDAYS.map((d) => (
              <div key={d} className="pb-1 text-center text-xs font-semibold text-slate-400">
                {d}
              </div>
            ))}
            {weeks.flatMap((week) =>
              week.map((date, di) => {
                const entry = date ? byDate.get(date) : undefined;
                return (
                  <div
                    key={(date ?? "empty") + di}
                    className={`min-h-[92px] rounded-lg border p-1.5 text-left ${
                      date ? "border-slate-200" : "border-transparent"
                    }`}
                  >
                    {date && (
                      <>
                        <div className="mb-1 text-[10px] font-semibold text-slate-400">
                          {parseYmd(date).getUTCDate()}
                        </div>
                        {entry ? (
                          <button
                            onClick={() => setSelected(entry)}
                            className={`w-full rounded-md border p-1.5 text-left text-[11px] leading-tight transition hover:shadow-sm ${
                              STATUS_STYLE[entry.status]
                            }`}
                          >
                            <div className="font-semibold">{entry.slot}</div>
                            <div className="line-clamp-2 opacity-80">{entry.topicText}</div>
                          </button>
                        ) : (
                          <div className="text-[10px] text-slate-300">—</div>
                        )}
                      </>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* Category balance */}
      {insights && insights.categoryBalance.length > 0 && (
        <div className="card p-4">
          <h2 className="mb-3 text-sm font-bold text-brand-ink">Category balance</h2>
          <div className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2 lg:grid-cols-3">
            {insights.categoryBalance.map((c) => {
              const pct = c.target > 0 ? Math.min(100, (c.count / (c.target * 2)) * 100) : 0;
              return (
                <div key={c.categoryName} className="flex items-center gap-2">
                  <span className="w-40 shrink-0 truncate text-xs text-slate-500">
                    {c.categoryName}
                  </span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                    <div className="h-full rounded-full bg-brand" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="w-6 text-right text-xs font-semibold text-slate-600">
                    {c.count}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Entry drawer */}
      {selected && (
        <EntryDrawer
          entry={selected}
          onClose={() => setSelected(null)}
          onPatch={patchEntry}
          onGenerate={generateEntry}
        />
      )}
    </div>
  );
}

function buildWeeks(entries: Entry[]): (string | null)[][] {
  if (entries.length === 0) return [];
  const dates = entries.map((e) => e.date).sort();
  const first = parseYmd(dates[0]);
  const last = parseYmd(dates[dates.length - 1]);
  // back up to Sunday
  const start = new Date(first);
  start.setUTCDate(start.getUTCDate() - start.getUTCDay());
  const weeks: (string | null)[][] = [];
  const cursor = new Date(start);
  while (cursor <= last || cursor.getUTCDay() !== 0) {
    const week: (string | null)[] = [];
    for (let i = 0; i < 7; i++) {
      const ymd = cursor.toISOString().slice(0, 10);
      const inRange = cursor >= first && cursor <= last;
      week.push(inRange ? ymd : null);
      cursor.setUTCDate(cursor.getUTCDate() + 1);
    }
    weeks.push(week);
    if (cursor > last) break;
  }
  return weeks;
}

function Stat({ label, value, good }: { label: string; value: number; good?: boolean }) {
  return (
    <div>
      <div className={`text-lg font-black ${good ? "text-emerald-600" : "text-brand-ink"}`}>
        {value}
      </div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}

const ACCENTS: Record<string, string> = {
  blue: "border-l-blue-400",
  amber: "border-l-amber-400",
  violet: "border-l-violet-400",
  emerald: "border-l-emerald-400",
};

function IntelCard({
  title,
  accent,
  children,
}: {
  title: string;
  accent: string;
  children: React.ReactNode;
}) {
  return (
    <div className={`card border-l-4 p-4 ${ACCENTS[accent]}`}>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</p>
      {children}
    </div>
  );
}

function EntryDrawer({
  entry,
  onClose,
  onPatch,
  onGenerate,
}: {
  entry: Entry;
  onClose: () => void;
  onPatch: (id: string, patch: Partial<{ status: CalendarStatus; note: string }>) => void;
  onGenerate: (id: string) => void;
}) {
  const [generating, setGenerating] = useState(false);
  return (
    <div className="fixed inset-0 z-30 flex justify-end bg-black/30" onClick={onClose}>
      <div
        className="h-full w-full max-w-md overflow-y-auto bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between">
          <div>
            <span className={`chip ${STATUS_STYLE[entry.status]}`}>{entry.status}</span>
            <h2 className="mt-2 text-lg font-bold text-brand-ink">{entry.slot}</h2>
            <p className="text-xs text-slate-500">
              {entry.date} · {entry.categoryName} · {entry.contentTypeName}
            </p>
          </div>
          <button onClick={onClose} className="text-2xl leading-none text-slate-400 hover:text-slate-600">
            ×
          </button>
        </div>

        <div className="mb-4 rounded-xl bg-slate-50 p-3">
          <p className="label">Topic</p>
          <p className="text-sm font-medium text-brand-ink">{entry.topicText}</p>
          <div className="mt-2 flex gap-4 text-xs text-slate-500">
            <span>Topic score: {entry.topicScore}</span>
            <span>Similarity: {Math.round(entry.duplicateScore * 100)}%</span>
          </div>
        </div>

        <p className="label">Approval workflow</p>
        <div className="mb-4 grid grid-cols-2 gap-2">
          <button className="btn-primary" onClick={() => onPatch(entry.id, { status: "approved" })}>
            Approve
          </button>
          <button className="btn-ghost" onClick={() => onPatch(entry.id, { status: "rejected" })}>
            Reject
          </button>
          <button className="btn-ghost" onClick={() => onPatch(entry.id, { status: "skipped" })}>
            Skip
          </button>
          <button className="btn-ghost" onClick={() => onPatch(entry.id, { status: "planned" })}>
            Reset
          </button>
        </div>

        <p className="label">Content</p>
        <button
          className="btn-primary w-full"
          disabled={generating}
          onClick={async () => {
            setGenerating(true);
            await onGenerate(entry.id);
            setGenerating(false);
          }}
        >
          {generating ? "Generating…" : entry.postId ? "Regenerate post + image" : "Generate post + image"}
        </button>
        {entry.postId && (
          <p className="mt-2 text-center text-xs text-emerald-600">
            ✓ Post generated. View it in Drafts.
          </p>
        )}
      </div>
    </div>
  );
}
