"use client";

import { useState } from "react";
import type { CampaignAsset } from "@/lib/types";

const KIND_LABEL: Record<string, string> = {
  linkedin_post: "LinkedIn Post",
  hr_email: "HR Email",
  linkedin_message: "LinkedIn Message",
  follow_up: "Follow-up Email",
  proposal: "Proposal",
  poll: "Poll",
  quiz: "Weekly Quiz",
  student_spotlight: "Student Spotlight",
  company_spotlight: "Company Spotlight",
  recruiter_insight: "Recruiter Insight",
};

const KIND_ICON: Record<string, string> = {
  linkedin_post: "in",
  hr_email: "@",
  linkedin_message: "💬",
  follow_up: "↩",
  proposal: "📄",
  poll: "📊",
  quiz: "❓",
  student_spotlight: "★",
  company_spotlight: "🏢",
  recruiter_insight: "🔎",
};

export function AssetCard({ asset }: { asset: CampaignAsset }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    const text = [asset.subject ? `Subject: ${asset.subject}` : "", asset.body]
      .filter(Boolean)
      .join("\n\n");
    navigator.clipboard?.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-soft text-xs font-bold text-brand">
            {KIND_ICON[asset.kind] ?? "•"}
          </span>
          <span className="text-sm font-bold text-brand-ink">
            {KIND_LABEL[asset.kind] ?? asset.kind}
          </span>
          {asset.scores && (
            <span className="chip">score {asset.scores.overall}</span>
          )}
          {asset.engine === "openai" && <span className="chip">AI</span>}
        </div>
        <button className="btn-ghost px-2.5 py-1 text-xs" onClick={copy}>
          {copied ? "Copied ✓" : "Copy"}
        </button>
      </div>

      {asset.subject && (
        <p className="mb-2 rounded-lg bg-slate-50 px-3 py-2 text-sm">
          <span className="font-semibold text-slate-500">Subject: </span>
          <span className="text-brand-ink">{asset.subject}</span>
        </p>
      )}

      <p className="linkedin-body text-sm leading-relaxed text-brand-ink">{asset.body}</p>

      {asset.meta?.pollOptions && (
        <div className="mt-3 space-y-1.5">
          {asset.meta.pollOptions.map((o, i) => (
            <div
              key={i}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600"
            >
              {o}
            </div>
          ))}
        </div>
      )}

      {asset.hashtags && asset.hashtags.length > 0 && (
        <p className="mt-2 text-sm font-medium text-brand">{asset.hashtags.join(" ")}</p>
      )}

      {asset.meta?.placeholders && asset.meta.placeholders.length > 0 && (
        <p className="mt-3 text-xs text-slate-400">
          Fill in: {asset.meta.placeholders.map((p) => `[${p}]`).join(", ")}
        </p>
      )}

      {asset.warnings && asset.warnings.length > 0 && (
        <ul className="mt-2 space-y-1">
          {asset.warnings.map((w, i) => (
            <li key={i} className="rounded-lg bg-amber-50 px-2 py-1 text-xs text-amber-800">
              {w}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
