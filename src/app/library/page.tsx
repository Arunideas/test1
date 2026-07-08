"use client";

import { useEffect, useState } from "react";
import type {
  BrandStyle,
  Category,
  ImageTemplate,
  PromptTemplate,
  Topic,
} from "@/lib/types";

interface Meta {
  categories: Category[];
  imageTemplates: ImageTemplate[];
  prompts: PromptTemplate[];
  topics: Topic[];
  brandStyle: BrandStyle;
}

function Section({
  title,
  desc,
  children,
}: {
  title: string;
  desc?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="card p-5">
      <h2 className="text-base font-bold text-brand-ink">{title}</h2>
      {desc && <p className="mt-0.5 text-xs text-slate-500">{desc}</p>}
      <div className="mt-3">{children}</div>
    </section>
  );
}

export default function LibraryPage() {
  const [meta, setMeta] = useState<Meta | null>(null);

  useEffect(() => {
    fetch("/api/meta").then((r) => r.json()).then(setMeta);
  }, []);

  if (!meta) return <p className="text-sm text-slate-500">Loading…</p>;

  const pillars = ["Students", "Companies", "Market", "Community"] as const;
  const brand = meta.brandStyle;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-brand-ink">Backend library</h1>

      <Section
        title="Brand style"
        desc="The permanent writing rules applied to every generated post."
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-sm font-semibold text-brand-ink">{brand.brandName}</p>
            <p className="mt-1 text-xs text-slate-600">{brand.positioningPrimary}</p>
            <p className="text-xs text-slate-500">{brand.positioningSecondary}</p>
            <p className="mt-3 label">Structure</p>
            <p className="text-xs text-slate-600">{brand.structure.join(" → ")}</p>
          </div>
          <div>
            <p className="label">Tone</p>
            <div className="flex flex-wrap gap-1">
              {brand.tone.map((t) => (
                <span key={t} className="chip">{t}</span>
              ))}
            </div>
            <p className="mt-3 label">Avoid</p>
            <div className="flex flex-wrap gap-1">
              {brand.avoidTone.map((t) => (
                <span key={t} className="chip border-rose-200 bg-rose-50 text-rose-600">
                  {t}
                </span>
              ))}
            </div>
            <p className="mt-3 label">Allowed CTAs</p>
            <div className="flex flex-wrap gap-1">
              {brand.allowedCtas.slice(0, 4).map((t) => (
                <span key={t} className="chip">{t}</span>
              ))}
            </div>
          </div>
        </div>
      </Section>

      <Section
        title={`Categories (${meta.categories.length})`}
        desc="Content pillars the platform balances across."
      >
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {pillars.map((pillar) => (
            <div key={pillar}>
              <p className="label">{pillar}</p>
              <div className="flex flex-wrap gap-1">
                {meta.categories
                  .filter((c) => c.pillar === pillar)
                  .map((c) => (
                    <span key={c.id} className="chip">{c.name}</span>
                  ))}
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Prompt library" desc="Reusable prompts per content type.">
        <div className="grid gap-3 sm:grid-cols-2">
          {meta.prompts.map((p) => (
            <div key={p.id} className="rounded-xl border border-slate-200 p-3">
              <p className="text-sm font-semibold text-brand-ink">{p.name}</p>
              <p className="mt-1 text-xs text-slate-500">{p.description}</p>
              <p className="mt-2 rounded-lg bg-slate-50 px-2 py-1.5 text-[11px] text-slate-500">
                {p.systemPrompt}
              </p>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Image templates" desc="Documentary-style, authentic — no glossy AI stock.">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {meta.imageTemplates.map((t) => (
            <div key={t.id} className="rounded-xl border border-slate-200 p-3">
              <p className="text-sm font-semibold text-brand-ink">{t.name}</p>
              <p className="mt-1 text-xs text-slate-500">{t.description}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title={`Topics (${meta.topics.length})`} desc="Tracked to prevent repeats.">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-slate-400">
              <tr className="border-b border-slate-200">
                <th className="py-2 pr-3 font-semibold">Topic</th>
                <th className="py-2 pr-3 font-semibold">Category</th>
                <th className="py-2 pr-3 font-semibold">Priority</th>
                <th className="py-2 pr-3 font-semibold">Status</th>
                <th className="py-2 pr-3 font-semibold">Last generated</th>
              </tr>
            </thead>
            <tbody>
              {meta.topics.map((t) => (
                <tr key={t.id} className="border-b border-slate-100">
                  <td className="py-2 pr-3 font-medium text-brand-ink">{t.topic}</td>
                  <td className="py-2 pr-3 text-slate-500">
                    {meta.categories.find((c) => c.id === t.categoryId)?.name ?? t.categoryId}
                  </td>
                  <td className="py-2 pr-3 text-slate-500">{t.priority}</td>
                  <td className="py-2 pr-3">
                    <span className="chip">{t.status}</span>
                  </td>
                  <td className="py-2 pr-3 text-slate-400">
                    {t.lastGeneratedAt
                      ? new Date(t.lastGeneratedAt).toLocaleDateString()
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}
