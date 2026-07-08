"use client";

import { useCallback, useEffect, useState } from "react";
import type { PublishJob, PublishStatus } from "@/lib/types";

interface Status {
  linkedin: { connected: boolean; simulated: boolean; authorUrn: string | null };
  counts: Record<string, number>;
  total: number;
}

const STATUS_STYLE: Record<PublishStatus, string> = {
  draft: "bg-slate-100 text-slate-600",
  pending_approval: "bg-amber-50 text-amber-700",
  scheduled: "bg-blue-50 text-blue-700",
  queued: "bg-violet-50 text-violet-700",
  publishing: "bg-violet-100 text-violet-700",
  published: "bg-emerald-50 text-emerald-700",
  failed: "bg-rose-50 text-rose-600",
  cancelled: "bg-slate-100 text-slate-400",
};

export default function PublishPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const [jobs, setJobs] = useState<PublishJob[]>([]);
  const [time, setTime] = useState("09:00");
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [s, j] = await Promise.all([
      fetch("/api/publish/status").then((r) => r.json()),
      fetch("/api/publish/jobs").then((r) => r.json()),
    ]);
    setStatus(s);
    setJobs(j.jobs ?? []);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000); // auto-refresh so scheduled jobs update live
    return () => clearInterval(t);
  }, [load]);

  async function action(id: string, act: "approve" | "cancel" | "retry") {
    await fetch(`/api/publish/jobs/${id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: act }),
    });
    load();
  }

  async function autoSchedule() {
    setBusy(true);
    try {
      const res = await fetch("/api/publish/auto-schedule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timeOfDay: time }),
      });
      const d = await res.json();
      alert(`Auto-scheduled ${d.created} approved calendar post(s) to LinkedIn.`);
      load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-brand-ink">Auto-publish to LinkedIn</h1>
        <p className="text-sm text-slate-500">
          Publish immediately, schedule ahead, require approval, and retry on failure.
        </p>
      </div>

      {/* Connection */}
      {status && (
        <div className="card p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span
                className={`flex h-10 w-10 items-center justify-center rounded-lg text-sm font-black text-white ${
                  status.linkedin.connected ? "bg-emerald-500" : "bg-slate-400"
                }`}
              >
                in
              </span>
              <div>
                <p className="text-sm font-bold text-brand-ink">
                  {status.linkedin.connected
                    ? "LinkedIn connected"
                    : "Simulation mode"}
                </p>
                <p className="text-xs text-slate-500">
                  {status.linkedin.connected
                    ? `Posting as ${status.linkedin.authorUrn}`
                    : "Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN to publish for real. Jobs still flow end-to-end here."}
                </p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs">
              {Object.entries(status.counts).map(([k, v]) => (
                <span key={k} className="chip">
                  {k.replace(/_/g, " ")}: {v}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Auto-schedule from calendar */}
      <div className="card flex flex-wrap items-center justify-between gap-3 p-4">
        <div>
          <p className="text-sm font-bold text-brand-ink">Auto-schedule the calendar</p>
          <p className="text-xs text-slate-500">
            Turn every approved/generated calendar post into a scheduled LinkedIn job.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs font-semibold text-slate-500">Time</label>
          <input
            type="time"
            value={time}
            onChange={(e) => setTime(e.target.value)}
            className="rounded-xl border border-slate-300 px-3 py-2 text-sm"
          />
          <button className="btn-primary" onClick={autoSchedule} disabled={busy}>
            {busy ? "Scheduling…" : "Auto-schedule"}
          </button>
        </div>
      </div>

      {/* Jobs */}
      <div className="card overflow-hidden">
        <div className="border-b border-slate-100 px-4 py-3 text-sm font-bold text-brand-ink">
          Publishing queue &amp; log
        </div>
        {jobs.length === 0 ? (
          <p className="p-6 text-center text-sm text-slate-500">
            No publish jobs yet. Publish a post from the Studio or auto-schedule the calendar.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {jobs.map((j) => (
              <li key={j.id} className="px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`chip ${STATUS_STYLE[j.status]}`}>
                        {j.status.replace(/_/g, " ")}
                      </span>
                      <span className="chip">{j.mode}</span>
                      {j.simulated && <span className="chip">simulated</span>}
                      {j.scheduledAt && j.status === "scheduled" && (
                        <span className="text-xs text-slate-400">
                          at {new Date(j.scheduledAt).toLocaleString()}
                        </span>
                      )}
                      {j.attempts > 0 && (
                        <span className="text-xs text-slate-400">
                          try {j.attempts}/{j.maxAttempts}
                        </span>
                      )}
                    </div>
                    <p className="mt-1 line-clamp-1 text-sm text-slate-600">
                      {j.text.split("\n")[0]}
                    </p>
                    {j.lastError && (
                      <p className="mt-0.5 line-clamp-1 text-xs text-rose-500">{j.lastError}</p>
                    )}
                    {j.postUrl && (
                      <a
                        href={j.postUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs font-medium text-brand hover:underline"
                      >
                        View post ↗
                      </a>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5">
                    {(j.status === "pending_approval" || j.status === "draft") && (
                      <button className="btn-primary px-3 py-1.5 text-xs" onClick={() => action(j.id, "approve")}>
                        Approve
                      </button>
                    )}
                    {j.status === "failed" && (
                      <button className="btn-ghost px-3 py-1.5 text-xs" onClick={() => action(j.id, "retry")}>
                        Retry
                      </button>
                    )}
                    {j.status !== "published" && j.status !== "cancelled" && (
                      <button className="btn-ghost px-3 py-1.5 text-xs" onClick={() => action(j.id, "cancel")}>
                        Cancel
                      </button>
                    )}
                    <button
                      className="btn-ghost px-3 py-1.5 text-xs"
                      onClick={() => setExpanded(expanded === j.id ? null : j.id)}
                    >
                      Log
                    </button>
                  </div>
                </div>
                {expanded === j.id && (
                  <ul className="mt-2 space-y-0.5 rounded-lg bg-slate-50 p-3 text-xs">
                    {j.log.map((l, i) => (
                      <li
                        key={i}
                        className={
                          l.level === "error"
                            ? "text-rose-600"
                            : l.level === "success"
                            ? "text-emerald-600"
                            : "text-slate-500"
                        }
                      >
                        {new Date(l.at).toLocaleTimeString()} · {l.message}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
