"use client";

import { useEffect, useMemo, useState } from "react";
import { AssetCard } from "@/components/AssetCard";
import type { Campaign, CampaignAssetKind, CampaignAudience } from "@/lib/types";

interface GrowthService {
  id: string;
  name: string;
  audience: CampaignAudience;
  blurb: string;
  goal: string;
  assetKinds: CampaignAssetKind[];
}

const AUDIENCE_TABS: { id: CampaignAudience; label: string; hint: string }[] = [
  { id: "employer", label: "Employers / HR", hint: "Educational post + outreach kit" },
  { id: "student", label: "Students", hint: "Post + poll + quiz" },
  { id: "community", label: "Community", hint: "Polls, quizzes, spotlights" },
];

const KIND_SHORT: Record<string, string> = {
  linkedin_post: "Post",
  hr_email: "Email",
  linkedin_message: "Message",
  follow_up: "Follow-up",
  proposal: "Proposal",
  poll: "Poll",
  quiz: "Quiz",
  student_spotlight: "Spotlight",
  company_spotlight: "Spotlight",
  recruiter_insight: "Insight",
};

export default function CampaignsPage() {
  const [services, setServices] = useState<GrowthService[]>([]);
  const [audience, setAudience] = useState<CampaignAudience>("employer");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [history, setHistory] = useState<Campaign[]>([]);

  useEffect(() => {
    fetch("/api/meta")
      .then((r) => r.json())
      .then((m) => setServices(m.growthServices ?? []));
    loadHistory();
  }, []);

  function loadHistory() {
    fetch("/api/campaigns")
      .then((r) => r.json())
      .then((d) => setHistory(d.campaigns ?? []));
  }

  const visible = useMemo(
    () => services.filter((s) => s.audience === audience),
    [services, audience]
  );

  async function generate(serviceId: string) {
    setBusyId(serviceId);
    setCampaign(null);
    try {
      const res = await fetch("/api/campaigns", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ serviceId }),
      });
      const data = await res.json();
      if (data.campaign) {
        setCampaign(data.campaign);
        loadHistory();
        setTimeout(
          () => document.getElementById("campaign-result")?.scrollIntoView({ behavior: "smooth" }),
          50
        );
      }
    } finally {
      setBusyId(null);
    }
  }

  async function remove(id: string) {
    await fetch(`/api/campaigns/${id}`, { method: "DELETE" });
    setHistory((h) => h.filter((c) => c.id !== id));
    if (campaign?.id === id) setCampaign(null);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-brand-ink">Growth Campaigns</h1>
        <p className="text-sm text-slate-500">
          One-click campaigns targeting HRs or students — turn content into platform growth.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {AUDIENCE_TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setAudience(t.id)}
            className={`rounded-xl border px-4 py-2 text-left transition ${
              audience === t.id
                ? "border-brand bg-brand-soft"
                : "border-slate-200 bg-white hover:border-slate-300"
            }`}
          >
            <div className="text-sm font-bold text-brand-ink">{t.label}</div>
            <div className="text-xs text-slate-500">{t.hint}</div>
          </button>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {visible.map((s) => (
          <div key={s.id} className="card flex flex-col p-5">
            <h3 className="text-base font-bold text-brand-ink">{s.name}</h3>
            <p className="mt-1 flex-1 text-sm text-slate-500">{s.blurb}</p>
            <div className="my-3 flex flex-wrap gap-1">
              {s.assetKinds.map((k) => (
                <span key={k} className="chip">
                  {KIND_SHORT[k] ?? k}
                </span>
              ))}
            </div>
            <button
              className="btn-primary w-full"
              disabled={busyId !== null}
              onClick={() => generate(s.id)}
            >
              {busyId === s.id ? "Generating…" : "Generate campaign"}
            </button>
          </div>
        ))}
      </div>

      {campaign && (
        <div id="campaign-result" className="space-y-4 border-t border-slate-200 pt-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-brand-ink">{campaign.name}</h2>
              <p className="text-sm text-slate-500">{campaign.goal}</p>
            </div>
            <span className="chip border-emerald-200 bg-emerald-50 text-emerald-700">
              {campaign.assets.length} assets ready
            </span>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            {campaign.assets.map((a) => (
              <AssetCard key={a.id} asset={a} />
            ))}
          </div>
        </div>
      )}

      {history.length > 0 && (
        <div className="border-t border-slate-200 pt-6">
          <h2 className="mb-3 text-sm font-bold text-brand-ink">Recent campaigns</h2>
          <div className="space-y-2">
            {history.map((c) => (
              <div
                key={c.id}
                className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-2.5"
              >
                <button className="text-left" onClick={() => setCampaign(c)}>
                  <span className="text-sm font-semibold text-brand-ink">{c.name}</span>
                  <span className="ml-2 text-xs text-slate-400">
                    {c.audience} · {c.assets.length} assets ·{" "}
                    {new Date(c.createdAt).toLocaleString()}
                  </span>
                </button>
                <button
                  className="text-xs font-semibold text-rose-500 hover:underline"
                  onClick={() => remove(c.id)}
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
