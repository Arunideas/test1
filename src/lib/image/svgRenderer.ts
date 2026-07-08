import type { ImageTemplate } from "../types";

export interface RenderInput {
  layout: ImageTemplate["layout"];
  topic: string;
  hook: string;
  lines: string[]; // supporting short lines pulled from the post
}

const W = 1200;
const H = 1200;

// Muted, paper/desk palette — deliberately not glossy or "AI beautiful".
const PALETTE = {
  paper: "#f3efe7",
  paper2: "#e9e3d6",
  ink: "#23303a",
  sub: "#5c6773",
  accent: "#0b5cff",
  warn: "#c0492f",
  ok: "#2f7d4f",
  card: "#fbf9f4",
  line: "#d7cfbf",
};

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function wrap(text: string, maxChars: number, maxLines: number): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  const out: string[] = [];
  let line = "";
  for (const w of words) {
    if ((line + " " + w).trim().length > maxChars) {
      if (line) out.push(line.trim());
      line = w;
    } else {
      line = (line + " " + w).trim();
    }
    if (out.length >= maxLines) break;
  }
  if (line && out.length < maxLines) out.push(line.trim());
  if (out.length === maxLines) {
    const last = out[maxLines - 1];
    if (last.length > maxChars - 1) out[maxLines - 1] = last.slice(0, maxChars - 1) + "…";
  }
  return out;
}

function textBlock(
  x: number,
  y: number,
  text: string,
  opts: {
    size: number;
    color: string;
    weight?: number;
    maxChars: number;
    maxLines: number;
    lineHeight?: number;
    anchor?: string;
  }
): string {
  const lines = wrap(text, opts.maxChars, opts.maxLines);
  const lh = opts.lineHeight ?? opts.size * 1.25;
  return lines
    .map(
      (ln, i) =>
        `<text x="${x}" y="${y + i * lh}" font-size="${opts.size}" fill="${
          opts.color
        }" font-weight="${opts.weight ?? 400}" text-anchor="${
          opts.anchor ?? "start"
        }" font-family="Georgia, 'Times New Roman', serif">${esc(ln)}</text>`
    )
    .join("");
}

function header(brand = "World of Interns"): string {
  return `
    <g>
      <rect x="80" y="80" width="46" height="46" rx="10" fill="${PALETTE.accent}"/>
      <text x="103" y="112" font-size="26" fill="#ffffff" font-weight="700" text-anchor="middle" font-family="Arial, sans-serif">W</text>
      <text x="140" y="112" font-size="26" fill="${PALETTE.ink}" font-weight="700" font-family="Arial, sans-serif">${esc(
    brand
  )}</text>
    </g>`;
}

function background(): string {
  return `
    <defs>
      <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="${PALETTE.paper}"/>
        <stop offset="1" stop-color="${PALETTE.paper2}"/>
      </linearGradient>
      <filter id="grain">
        <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch"/>
        <feColorMatrix type="saturate" values="0"/>
        <feComponentTransfer><feFuncA type="linear" slope="0.05"/></feComponentTransfer>
        <feComposite operator="over" in2="SourceGraphic"/>
      </filter>
    </defs>
    <rect width="${W}" height="${H}" fill="url(#bg)"/>
    <rect width="${W}" height="${H}" filter="url(#grain)" opacity="0.06"/>`;
}

function footer(): string {
  return `<text x="${W / 2}" y="${
    H - 70
  }" font-size="22" fill="${PALETTE.sub}" text-anchor="middle" font-family="Arial, sans-serif">worldofinterns.in  ·  practical, not promotional</text>`;
}

function shortLines(lines: string[], n: number): string[] {
  return lines
    .map((l) => l.replace(/\s+/g, " ").trim())
    .filter((l) => l.length > 2 && l.length < 120)
    .slice(0, n);
}

function renderStatistics(input: RenderInput): string {
  const stat = (input.lines.find((l) => /\d/.test(l)) ?? "7 seconds")
    .match(/\d+\s*\w+/)?.[0] ?? "7s";
  return `
    ${header()}
    ${textBlock(80, 260, input.topic, {
      size: 40,
      color: PALETTE.sub,
      maxChars: 40,
      maxLines: 2,
      weight: 700,
    })}
    <text x="${W / 2}" y="640" font-size="300" fill="${
    PALETTE.ink
  }" font-weight="800" text-anchor="middle" font-family="Arial, sans-serif">${esc(
    stat
  )}</text>
    ${textBlock(80, 760, input.hook, {
      size: 44,
      color: PALETTE.ink,
      maxChars: 34,
      maxLines: 3,
    })}
    ${footer()}`;
}

function renderChecklist(input: RenderInput): string {
  const items = shortLines(input.lines, 4);
  const rows = items
    .map((it, i) => {
      const y = 420 + i * 150;
      return `
      <rect x="80" y="${y - 44}" width="44" height="44" rx="8" fill="none" stroke="${
        PALETTE.ink
      }" stroke-width="4"/>
      <path d="M90 ${y - 22} l12 14 l24 -30" fill="none" stroke="${
        PALETTE.ok
      }" stroke-width="6" stroke-linecap="round"/>
      ${textBlock(150, y - 8, it, {
        size: 38,
        color: PALETTE.ink,
        maxChars: 40,
        maxLines: 1,
      })}`;
    })
    .join("");
  return `
    ${header()}
    ${textBlock(80, 280, input.topic, {
      size: 52,
      color: PALETTE.ink,
      maxChars: 30,
      maxLines: 2,
      weight: 800,
    })}
    ${rows}
    ${footer()}`;
}

function renderBeforeAfter(input: RenderInput): string {
  const mid = W / 2;
  return `
    ${header()}
    ${textBlock(80, 260, input.topic, {
      size: 46,
      color: PALETTE.ink,
      maxChars: 34,
      maxLines: 2,
      weight: 800,
    })}
    <rect x="80" y="340" width="480" height="720" rx="16" fill="${
      PALETTE.card
    }" stroke="${PALETTE.line}" stroke-width="3"/>
    <rect x="${mid + 20}" y="340" width="480" height="720" rx="16" fill="${
    PALETTE.card
  }" stroke="${PALETTE.line}" stroke-width="3"/>
    <text x="320" y="410" font-size="30" fill="${
      PALETTE.warn
    }" font-weight="700" text-anchor="middle" font-family="Arial, sans-serif">BEFORE</text>
    <text x="${mid + 260}" y="410" font-size="30" fill="${
    PALETTE.ok
  }" font-weight="700" text-anchor="middle" font-family="Arial, sans-serif">AFTER</text>
    ${textBlock(110, 480, "Objective: seeking a challenging role to grow my skills…", {
      size: 26,
      color: PALETTE.sub,
      maxChars: 30,
      maxLines: 4,
    })}
    ${textBlock(mid + 50, 480, "Final year CS. Built 3 projects. Shipped a tool used by 40 students.", {
      size: 26,
      color: PALETTE.ink,
      maxChars: 30,
      maxLines: 5,
      weight: 700,
    })}
    ${footer()}`;
}

function renderQuestion(input: RenderInput): string {
  return `
    ${header()}
    <rect x="120" y="360" width="960" height="520" rx="24" fill="${
      PALETTE.card
    }" stroke="${PALETTE.line}" stroke-width="3"/>
    <text x="170" y="470" font-size="120" fill="${
      PALETTE.accent
    }" font-weight="800" font-family="Georgia, serif">“</text>
    ${textBlock(180, 560, input.hook || input.topic, {
      size: 54,
      color: PALETTE.ink,
      maxChars: 26,
      maxLines: 4,
      weight: 700,
    })}
    ${footer()}`;
}

function renderTopList(input: RenderInput): string {
  const items = shortLines(input.lines, 3);
  while (items.length < 3) items.push("");
  const rows = items
    .map((it, i) => {
      const y = 430 + i * 180;
      return `
      <circle cx="120" cy="${y}" r="38" fill="${PALETTE.accent}"/>
      <text x="120" y="${
        y + 14
      }" font-size="40" fill="#fff" font-weight="800" text-anchor="middle" font-family="Arial, sans-serif">${
        i + 1
      }</text>
      ${textBlock(190, y + 14, it || "…", {
        size: 40,
        color: PALETTE.ink,
        maxChars: 34,
        maxLines: 1,
      })}`;
    })
    .join("");
  return `
    ${header()}
    ${textBlock(80, 300, input.topic, {
      size: 54,
      color: PALETTE.ink,
      maxChars: 28,
      maxLines: 2,
      weight: 800,
    })}
    ${rows}
    ${footer()}`;
}

function renderTimeline(input: RenderInput): string {
  const steps: Array<[string, string]> = [
    ["Week 1", "Learn the basics from one free course."],
    ["Week 2", "Rebuild one thing you use daily."],
    ["Week 3", "Break it, then fix it."],
    ["Week 4", "Write down what you learned in public."],
  ];
  const rows = steps
    .map(([s, desc], i) => {
      const y = 400 + i * 150;
      return `
      <circle cx="130" cy="${y}" r="16" fill="${PALETTE.accent}"/>
      ${i < 3 ? `<line x1="130" y1="${y + 18}" x2="130" y2="${y + 132}" stroke="${PALETTE.line}" stroke-width="4"/>` : ""}
      <text x="180" y="${y - 6}" font-size="30" fill="${
        PALETTE.accent
      }" font-weight="700" font-family="Arial, sans-serif">${s}</text>
      ${textBlock(180, y + 30, desc, {
        size: 30,
        color: PALETTE.ink,
        maxChars: 44,
        maxLines: 1,
      })}`;
    })
    .join("");
  return `
    ${header()}
    ${textBlock(80, 300, input.topic, {
      size: 52,
      color: PALETTE.ink,
      maxChars: 30,
      maxLines: 2,
      weight: 800,
    })}
    ${rows}
    ${footer()}`;
}

function renderComparison(input: RenderInput): string {
  const mid = W / 2;
  return `
    ${header()}
    ${textBlock(80, 280, input.topic, {
      size: 48,
      color: PALETTE.ink,
      maxChars: 32,
      maxLines: 2,
      weight: 800,
    })}
    <line x1="${mid}" y1="360" x2="${mid}" y2="1040" stroke="${
    PALETTE.line
  }" stroke-width="3"/>
    <text x="300" y="430" font-size="34" fill="${
      PALETTE.sub
    }" font-weight="700" text-anchor="middle" font-family="Arial, sans-serif">What students show</text>
    <text x="${mid + 300}" y="430" font-size="34" fill="${
    PALETTE.accent
  }" font-weight="700" text-anchor="middle" font-family="Arial, sans-serif">What recruiters want</text>
    ${textBlock(100, 520, "Long summary. Generic objective. Skills with no proof.", {
      size: 30,
      color: PALETTE.sub,
      maxChars: 28,
      maxLines: 5,
    })}
    ${textBlock(mid + 40, 520, "One relevant project. One result. Matching keywords.", {
      size: 30,
      color: PALETTE.ink,
      maxChars: 28,
      maxLines: 5,
      weight: 700,
    })}
    ${footer()}`;
}

function renderQuote(input: RenderInput): string {
  return `
    ${header()}
    ${textBlock(120, 520, input.hook || input.topic, {
      size: 62,
      color: PALETTE.ink,
      maxChars: 24,
      maxLines: 5,
      weight: 700,
    })}
    <rect x="120" y="560" width="120" height="8" fill="${PALETTE.accent}" opacity="0"/>
    <text x="120" y="1000" font-size="28" fill="${
      PALETTE.sub
    }" font-family="Arial, sans-serif">A pattern seen across many students — not one invented story.</text>
    ${footer()}`;
}

export function renderSvg(input: RenderInput): string {
  let inner = "";
  switch (input.layout) {
    case "statistics":
      inner = renderStatistics(input);
      break;
    case "checklist":
      inner = renderChecklist(input);
      break;
    case "before_after":
      inner = renderBeforeAfter(input);
      break;
    case "question_card":
      inner = renderQuestion(input);
      break;
    case "top_list":
      inner = renderTopList(input);
      break;
    case "timeline":
      inner = renderTimeline(input);
      break;
    case "comparison":
      inner = renderComparison(input);
      break;
    case "quote":
      inner = renderQuote(input);
      break;
    default:
      inner = renderQuestion(input);
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img">
    ${background()}
    ${inner}
  </svg>`;
}

export function svgToDataUri(svg: string): string {
  const base64 = Buffer.from(svg, "utf8").toString("base64");
  return `data:image/svg+xml;base64,${base64}`;
}
