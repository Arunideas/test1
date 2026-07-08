"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { LinkedInPreview } from "@/components/LinkedInPreview";
import { ScorePanel } from "@/components/ScorePanel";
import type {
  Audience,
  Category,
  ContentTypeId,
  GeneratedImage,
  GeneratedPost,
  ImageTemplate,
  PromptTemplate,
  Topic,
} from "@/lib/types";

interface ContentTypeDef {
  id: ContentTypeId;
  name: string;
  defaultAudience: Audience;
  defaultImageTemplateId: string;
  blurb: string;
  suggestedCategoryIds: string[];
}

interface Meta {
  contentTypes: ContentTypeDef[];
  categories: Category[];
  imageTemplates: ImageTemplate[];
  prompts: PromptTemplate[];
  topics: Topic[];
  engine: "openai" | "rule-based";
}

type Result = { post: GeneratedPost; image: GeneratedImage | null };

export default function StudioPage() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [contentTypeId, setContentTypeId] = useState<ContentTypeId>("resume_review");
  const [topicMode, setTopicMode] = useState<"auto" | "pick" | "custom">("auto");
  const [topicId, setTopicId] = useState<string>("");
  const [customTopic, setCustomTopic] = useState<string>("");
  const [categoryId, setCategoryId] = useState<string>("");
  const [audience, setAudience] = useState<Audience>("students");
  const [extra, setExtra] = useState<string>("");

  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState<number | null>(null);

  const [editing, setEditing] = useState(false);
  const [editBody, setEditBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetch("/api/meta")
      .then((r) => r.json())
      .then((m: Meta) => {
        setMeta(m);
        const ct = m.contentTypes.find((c) => c.id === contentTypeId);
        if (ct) setAudience(ct.defaultAudience);
      })
      .catch(() => setError("Failed to load configuration."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const topicsForType = useMemo(() => {
    if (!meta) return [];
    const ct = meta.contentTypes.find((c) => c.id === contentTypeId);
    const scope = ct?.suggestedCategoryIds ?? [];
    const inScope = meta.topics.filter((t) => scope.includes(t.categoryId));
    return inScope.length ? inScope : meta.topics;
  }, [meta, contentTypeId]);

  function onSelectType(id: ContentTypeId) {
    setContentTypeId(id);
    if (!meta) return;
    const ct = meta.contentTypes.find((c) => c.id === id);
    if (ct) setAudience(ct.defaultAudience);
    setTopicId("");
  }

  async function onGenerate() {
    if (!meta) return;
    setGenerating(true);
    setError(null);
    setResult(null);
    setEditing(false);
    setElapsed(null);
    const start = Date.now();
    timerRef.current = setInterval(() => setElapsed((Date.now() - start) / 1000), 100);

    const payload: Record<string, unknown> = { contentTypeId, audience };
    if (topicMode === "pick" && topicId) payload.topicId = topicId;
    if (topicMode === "custom" && customTopic.trim()) {
      payload.topic = customTopic.trim();
      if (categoryId) payload.categoryId = categoryId;
    }
    if (extra.trim()) payload.extraContext = extra.trim();

    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error((await res.json()).error || "Generation failed");
      const data = (await res.json()) as Result;
      setResult(data);
      setEditBody(data.post.body);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      if (timerRef.current) clearInterval(timerRef.current);
      setElapsed((Date.now() - start) / 1000);
      setGenerating(false);
    }
  }

  async function onSaveEdit() {
    if (!result) return;
    setBusy(true);
    try {
      const res = await fetch(`/api/posts/${result.post.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body: editBody, note: "Manual edit" }),
      });
      const data = await res.json();
      if (data.post) {
        setResult({ post: data.post, image: result.image });
        setEditing(false);
      }
    } finally {
      setBusy(false);
    }
  }

  async function onRegenImage(templateId?: string) {
    if (!result) return;
    setBusy(true);
    try {
      const res = await fetch(`/api/posts/${result.post.id}/image`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ templateId }),
      });
      const data = await res.json();
      if (data.image) setResult({ post: data.post, image: data.image });
    } finally {
      setBusy(false);
    }
  }

  function onCopy() {
    if (!result) return;
    const text = `${result.post.body}\n\n${result.post.hashtags.join(" ")}`;
    navigator.clipboard?.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const post = result?.post;
  const image = result?.image;

  return (
    <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
      {/* Left: generator */}
      <section className="card h-fit p-5">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-lg font-bold text-brand-ink">Content Studio</h1>
          {meta && (
            <span className="chip">
              {meta.engine === "openai" ? "OpenAI" : "Offline engine"}
            </span>
          )}
        </div>

        <label className="label">Content type</label>
        <div className="mb-4 grid grid-cols-2 gap-2">
          {meta?.contentTypes.map((ct) => (
            <button
              key={ct.id}
              onClick={() => onSelectType(ct.id)}
              className={`rounded-xl border px-3 py-2 text-left text-xs font-semibold transition ${
                contentTypeId === ct.id
                  ? "border-brand bg-brand-soft text-brand"
                  : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
              }`}
            >
              {ct.name}
            </button>
          ))}
        </div>

        <label className="label">Topic</label>
        <div className="mb-2 flex gap-1 rounded-xl bg-slate-100 p-1 text-xs font-semibold">
          {(["auto", "pick", "custom"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setTopicMode(m)}
              className={`flex-1 rounded-lg px-2 py-1.5 capitalize transition ${
                topicMode === m ? "bg-white text-brand shadow-sm" : "text-slate-500"
              }`}
            >
              {m === "auto" ? "Auto-pick" : m}
            </button>
          ))}
        </div>

        {topicMode === "auto" && (
          <p className="mb-4 text-xs text-slate-500">
            We pick a topic that hasn&apos;t been used recently and fits this content
            type — balancing your categories automatically.
          </p>
        )}

        {topicMode === "pick" && (
          <select
            className="select mb-4"
            value={topicId}
            onChange={(e) => setTopicId(e.target.value)}
          >
            <option value="">Select a topic…</option>
            {topicsForType.map((t) => (
              <option key={t.id} value={t.id}>
                {t.topic}
              </option>
            ))}
          </select>
        )}

        {topicMode === "custom" && (
          <div className="mb-4 space-y-2">
            <input
              className="input"
              placeholder="e.g. How to explain a project gap"
              value={customTopic}
              onChange={(e) => setCustomTopic(e.target.value)}
            />
            <select
              className="select"
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
            >
              <option value="">Auto category</option>
              {meta?.categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.pillar} · {c.name}
                </option>
              ))}
            </select>
          </div>
        )}

        <label className="label">Audience</label>
        <select
          className="select mb-4"
          value={audience}
          onChange={(e) => setAudience(e.target.value as Audience)}
        >
          <option value="students">Students</option>
          <option value="companies">Companies</option>
          <option value="market">Market</option>
          <option value="community">Community</option>
        </select>

        <label className="label">Extra context (optional)</label>
        <textarea
          className="textarea mb-4"
          rows={2}
          placeholder="Any angle, data point, or constraint to include."
          value={extra}
          onChange={(e) => setExtra(e.target.value)}
        />

        <button
          className="btn-primary w-full"
          onClick={onGenerate}
          disabled={generating || !meta}
        >
          {generating ? "Generating…" : "Generate post + image"}
        </button>

        {elapsed !== null && (
          <p className="mt-2 text-center text-xs text-slate-500">
            {generating ? "Working" : "Done"} in {elapsed.toFixed(1)}s
            {!generating && elapsed < 120 ? " · under 2 min ✅" : ""}
          </p>
        )}
        {error && (
          <p className="mt-2 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-600">
            {error}
          </p>
        )}
      </section>

      {/* Right: preview + tools */}
      <section className="space-y-4">
        {!post && (
          <div className="card flex min-h-[400px] flex-col items-center justify-center p-8 text-center">
            <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-soft text-2xl">
              ✍️
            </div>
            <h2 className="text-lg font-bold text-brand-ink">
              Generate a LinkedIn-ready post in under 2 minutes
            </h2>
            <p className="mt-2 max-w-md text-sm text-slate-500">
              Pick a content type and topic, then generate. You&apos;ll get a
              human-sounding post in the World of Interns voice, an authentic
              supporting image, and a quality score — ready to preview, edit and save.
            </p>
          </div>
        )}

        {post && (
          <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
            <div className="space-y-4">
              {editing ? (
                <div className="card p-4">
                  <label className="label">Edit post</label>
                  <textarea
                    className="textarea font-mono text-[13px]"
                    rows={16}
                    value={editBody}
                    onChange={(e) => setEditBody(e.target.value)}
                  />
                  <div className="mt-3 flex gap-2">
                    <button className="btn-primary" onClick={onSaveEdit} disabled={busy}>
                      {busy ? "Saving…" : "Save changes"}
                    </button>
                    <button
                      className="btn-ghost"
                      onClick={() => {
                        setEditBody(post.body);
                        setEditing(false);
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <LinkedInPreview
                  body={post.body}
                  hashtags={post.hashtags}
                  imageSvg={image?.svg}
                  imageAlt={image?.altText}
                />
              )}

              <div className="flex flex-wrap gap-2">
                {!editing && (
                  <button className="btn-ghost" onClick={() => setEditing(true)}>
                    ✎ Edit
                  </button>
                )}
                <button className="btn-ghost" onClick={() => onRegenImage()} disabled={busy}>
                  🔄 New image
                </button>
                <button className="btn-ghost" onClick={onGenerate} disabled={generating}>
                  ↻ Regenerate
                </button>
                <button className="btn-ghost" onClick={onCopy}>
                  {copied ? "Copied ✓" : "Copy text"}
                </button>
              </div>

              {image && (
                <div className="card p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="label mb-0">Image template</span>
                    <span className="chip">
                      {image.source === "openai" ? "AI photo" : "Local render"}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {meta?.imageTemplates.map((t) => (
                      <button
                        key={t.id}
                        onClick={() => onRegenImage(t.id)}
                        disabled={busy}
                        className={`rounded-lg border px-2.5 py-1 text-xs font-medium transition ${
                          t.id === image.templateId
                            ? "border-brand bg-brand-soft text-brand"
                            : "border-slate-200 text-slate-500 hover:border-slate-300"
                        }`}
                      >
                        {t.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Insights */}
            <div className="space-y-4">
              <div className="card p-4">
                <ScorePanel scores={post.scores} />
              </div>

              <div className="card p-4 text-sm">
                <div className="mb-2 flex items-center justify-between">
                  <span className="label mb-0">Details</span>
                  <span className="chip">{post.engine}</span>
                </div>
                <dl className="space-y-1.5 text-xs text-slate-600">
                  <Detail k="Topic" v={post.topic} />
                  <Detail k="Category" v={meta?.categories.find((c) => c.id === post.categoryId)?.name ?? post.categoryId} />
                  <Detail k="Words" v={String(post.wordCount)} />
                  <Detail k="Est. read" v={`${post.readTimeSeconds}s`} />
                  <Detail k="CTA" v={post.cta} />
                </dl>
              </div>

              <div className="card p-4">
                <span className="label">Brand review</span>
                {post.warnings.length === 0 ? (
                  <p className="rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
                    ✓ Passes the writing-style rules.
                  </p>
                ) : (
                  <ul className="space-y-1.5">
                    {post.warnings.map((w, i) => (
                      <li
                        key={i}
                        className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800"
                      >
                        {w}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {post.versions.length > 1 && (
                <div className="card p-4">
                  <span className="label">Version history</span>
                  <ul className="space-y-1 text-xs text-slate-600">
                    {[...post.versions].reverse().map((v) => (
                      <li key={v.version} className="flex justify-between">
                        <span>v{v.version} · {v.note}</span>
                        <span className="text-slate-400">
                          {new Date(v.createdAt).toLocaleTimeString()}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="card p-4">
                <span className="label">Image prompt</span>
                <p className="text-xs leading-relaxed text-slate-500">{post.imagePrompt}</p>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function Detail({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="shrink-0 text-slate-400">{k}</dt>
      <dd className="text-right font-medium text-slate-700">{v}</dd>
    </div>
  );
}
