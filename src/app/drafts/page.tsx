"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PostImage } from "@/components/PostImage";
import type { GeneratedImage, GeneratedPost } from "@/lib/types";

type PostWithImage = GeneratedPost & { image: GeneratedImage | null };

export default function DraftsPage() {
  const [posts, setPosts] = useState<PostWithImage[]>([]);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    fetch("/api/posts")
      .then((r) => r.json())
      .then((d) => setPosts(d.posts ?? []))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function remove(id: string) {
    await fetch(`/api/posts/${id}`, { method: "DELETE" });
    setPosts((p) => p.filter((x) => x.id !== id));
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold text-brand-ink">Saved drafts</h1>
        <Link href="/" className="btn-primary">
          + New post
        </Link>
      </div>

      {loading && <p className="text-sm text-slate-500">Loading…</p>}
      {!loading && posts.length === 0 && (
        <div className="card p-10 text-center text-sm text-slate-500">
          No drafts yet. Generate your first post in the Studio.
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {posts.map((p) => (
          <div key={p.id} className="card flex flex-col overflow-hidden">
            {p.image && (
              <div className="aspect-square w-full border-b border-slate-100 bg-slate-50">
                <PostImage
                  svg={p.image.svg}
                  alt={p.image.altText}
                  className="h-full w-full [&>svg]:h-full [&>svg]:w-full"
                />
              </div>
            )}
            <div className="flex flex-1 flex-col p-4">
              <div className="mb-1 flex items-center gap-2">
                <span className="chip">{p.contentTypeId.replace(/_/g, " ")}</span>
                <span className="chip">score {p.scores.overall}</span>
              </div>
              <h3 className="text-sm font-bold text-brand-ink">{p.title}</h3>
              <p className="linkedin-body mt-1 line-clamp-4 flex-1 text-xs text-slate-500">
                {p.body}
              </p>
              <div className="mt-3 flex items-center justify-between text-xs">
                <span className="text-slate-400">
                  {new Date(p.createdAt).toLocaleDateString()} · {p.wordCount} words
                </span>
                <button
                  className="font-semibold text-rose-500 hover:underline"
                  onClick={() => remove(p.id)}
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
