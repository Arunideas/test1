import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "World of Interns · Content Intelligence",
  description:
    "Generate high-quality, human-like LinkedIn posts with authentic supporting images in a consistent brand voice.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/80 backdrop-blur">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
            <Link href="/" className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand text-lg font-black text-white">
                W
              </span>
              <span className="leading-tight">
                <span className="block text-sm font-bold text-brand-ink">
                  World of Interns
                </span>
                <span className="block text-xs text-slate-500">
                  Content Intelligence
                </span>
              </span>
            </Link>
            <nav className="flex items-center gap-1 text-sm font-medium">
              <Link className="rounded-lg px-3 py-2 text-slate-600 hover:bg-slate-100" href="/">
                Studio
              </Link>
              <Link className="rounded-lg px-3 py-2 text-slate-600 hover:bg-slate-100" href="/calendar">
                Calendar
              </Link>
              <Link className="rounded-lg px-3 py-2 text-slate-600 hover:bg-slate-100" href="/campaigns">
                Campaigns
              </Link>
              <Link className="rounded-lg px-3 py-2 text-slate-600 hover:bg-slate-100" href="/drafts">
                Drafts
              </Link>
              <Link className="rounded-lg px-3 py-2 text-slate-600 hover:bg-slate-100" href="/library">
                Library
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 py-10 text-center text-xs text-slate-400">
          Practical, not promotional · Every post should be valuable even without the brand name.
        </footer>
      </body>
    </html>
  );
}
