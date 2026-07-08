"use client";

import { PostImage } from "./PostImage";

export function LinkedInPreview({
  body,
  hashtags,
  imageSvg,
  imageAlt,
}: {
  body: string;
  hashtags: string[];
  imageSvg?: string | null;
  imageAlt?: string;
}) {
  const tagLine = hashtags.join(" ");
  return (
    <div className="mx-auto w-full max-w-md overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center gap-3 p-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand text-lg font-black text-white">
          W
        </div>
        <div className="leading-tight">
          <div className="flex items-center gap-1 text-sm font-semibold text-brand-ink">
            World of Interns
          </div>
          <div className="text-xs text-slate-500">
            Employability in the AI era · Follower
          </div>
          <div className="text-xs text-slate-400">Now · 🌐</div>
        </div>
      </div>

      <div className="px-4 pb-3">
        <p className="linkedin-body text-[15px] leading-relaxed text-brand-ink">
          {body}
        </p>
        {tagLine && (
          <p className="mt-2 text-[15px] font-medium text-brand">{tagLine}</p>
        )}
      </div>

      {imageSvg && (
        <div className="border-y border-slate-100 bg-slate-50">
          <PostImage svg={imageSvg} alt={imageAlt} className="aspect-square w-full [&>svg]:h-full [&>svg]:w-full" />
        </div>
      )}

      <div className="flex items-center justify-between px-4 py-2 text-xs text-slate-500">
        <span>👍 ❤️ 💡 128</span>
        <span>24 comments · 12 reposts</span>
      </div>
      <div className="grid grid-cols-4 border-t border-slate-100 text-sm font-medium text-slate-500">
        {["Like", "Comment", "Repost", "Send"].map((a) => (
          <div key={a} className="py-2 text-center hover:bg-slate-50">
            {a}
          </div>
        ))}
      </div>
    </div>
  );
}
