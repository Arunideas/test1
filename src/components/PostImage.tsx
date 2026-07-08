"use client";

export function PostImage({
  svg,
  alt,
  className,
}: {
  svg?: string | null;
  alt?: string;
  className?: string;
}) {
  if (!svg) {
    return (
      <div className={`flex items-center justify-center bg-slate-100 text-sm text-slate-400 ${className ?? ""}`}>
        No image yet
      </div>
    );
  }
  const isMarkup = svg.trim().startsWith("<svg");
  if (isMarkup) {
    return (
      <div
        className={className}
        role="img"
        aria-label={alt}
        // Locally rendered SVG composition (no external request).
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    );
  }
  // data: URI or remote URL (e.g. OpenAI image)
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={svg} alt={alt ?? ""} className={className} />;
}
