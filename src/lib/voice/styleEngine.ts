import type { BrandStyle, QualityScores } from "../types";

export interface StyleAnalysis {
  scores: QualityScores;
  warnings: string[];
  wordCount: number;
  readTimeSeconds: number;
  paragraphs: string[];
}

const AI_TELLS = [
  "as an ai",
  "as a language model",
  "in conclusion",
  "furthermore",
  "moreover",
  "delve",
  "in today's fast-paced world",
  "in the ever-evolving",
  "it is important to note",
  "navigating the",
  "tapestry",
  "realm of",
];

const MOTIVATIONAL = [
  "believe in yourself",
  "chase your dreams",
  "never give up",
  "the sky is the limit",
  "you got this",
  "rise and grind",
  "no pain no gain",
  "your journey",
  "your best self",
  "shine",
];

const PROMO = [
  "register",
  "sign up",
  "buy",
  "subscribe",
  "our platform",
  "join now",
  "we offer",
  "our product",
  "book a demo",
  "visit our website",
  "dm us",
  "link in bio",
];

const EVIDENCE_MARKERS = [
  /\b\d+%/,
  /\b\d+\s*(out of|\/)\s*\d+/i,
  /\b\d+\s*(seconds|minutes|days|weeks|months|resumes|applications|students|recruiters|roles)\b/i,
  /\brecruiters?\b/i,
  /\bhiring\b/i,
];

const ACTION_MARKERS = [
  /\btry\b/i,
  /\bstart\b/i,
  /\bwrite\b/i,
  /\breplace\b/i,
  /\bcheck\b/i,
  /\badd\b/i,
  /\bremove\b/i,
  /\bpractice\b/i,
  /\buse\b/i,
  /\bpick\b/i,
  /\bstep\b/i,
];

function countMatches(text: string, needles: string[]): string[] {
  const lower = text.toLowerCase();
  return needles.filter((n) => lower.includes(n.toLowerCase()));
}

function sentences(text: string): string[] {
  return text
    .replace(/\n+/g, " ")
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function clamp(n: number, lo = 0, hi = 100): number {
  return Math.max(lo, Math.min(hi, Math.round(n)));
}

/** Approximate rendered lines for a paragraph on a ~60 char line width. */
function estimatedLines(paragraph: string): number {
  const rawLines = paragraph.split("\n");
  let total = 0;
  for (const line of rawLines) {
    total += Math.max(1, Math.ceil(line.length / 60));
  }
  return total;
}

export function analyzeText(body: string, brand: BrandStyle): StyleAnalysis {
  const warnings: string[] = [];
  const paragraphs = body
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean);

  const words = body.split(/\s+/).filter(Boolean);
  const wordCount = words.length;
  const readTimeSeconds = Math.max(10, Math.round((wordCount / 200) * 60));

  // Banned phrases (brand-defined) + generic promo/motivational/AI tells.
  const banned = countMatches(body, brand.bannedPhrases);
  if (banned.length) {
    warnings.push(`Remove sales/hype phrases: ${banned.join(", ")}`);
  }

  const aiTells = countMatches(body, AI_TELLS);
  if (aiTells.length) {
    warnings.push(`Sounds AI-generated: ${aiTells.join(", ")}`);
  }

  const motivational = countMatches(body, MOTIVATIONAL);
  if (motivational.length) {
    warnings.push(`Too motivational: ${motivational.join(", ")}`);
  }

  const promo = countMatches(body, PROMO);

  // Fake first-name detection (avoid invented characters).
  const nameHits = new Set<string>();
  for (const name of brand.bannedNames) {
    const re = new RegExp(`\\b${name}\\b`, "i");
    if (re.test(body)) nameHits.add(name);
  }
  if (nameHits.size) {
    warnings.push(
      `Avoid invented names (${[...nameHits].join(
        ", "
      )}). Use "a final year student" instead.`
    );
  }

  // Paragraph length rule (max lines per paragraph).
  const longParas = paragraphs.filter(
    (p) => estimatedLines(p) > brand.maxLinesPerParagraph
  );
  if (longParas.length) {
    warnings.push(
      `${longParas.length} paragraph(s) exceed ${brand.maxLinesPerParagraph} lines. Break them up.`
    );
  }

  // Sentence length rule (keep sentences short).
  const sents = sentences(body);
  const longSentences = sents.filter((s) => s.split(/\s+/).length > 22);
  if (longSentences.length) {
    warnings.push(`${longSentences.length} long sentence(s). Split into shorter lines.`);
  }

  // CTA check: should contain a question that is not a hard sell.
  const hasQuestion = /\?/.test(body);
  if (!hasQuestion) {
    warnings.push("Missing a soft question CTA (e.g. \"What do you think?\").");
  }

  // ---- Scoring ----
  const evidenceCount = EVIDENCE_MARKERS.filter((re) => re.test(body)).length;
  const actionCount = ACTION_MARKERS.filter((re) => re.test(body)).length;

  const educational = clamp(
    45 + evidenceCount * 12 + Math.min(paragraphs.length, 5) * 4 - aiTells.length * 15
  );
  const trust = clamp(
    60 + evidenceCount * 10 - banned.length * 20 - promo.length * 12 - nameHits.size * 15
  );
  const actionable = clamp(
    40 + actionCount * 10 + (hasQuestion ? 15 : 0)
  );
  const authentic = clamp(
    85 - aiTells.length * 20 - motivational.length * 20 - nameHits.size * 15
  );
  const avgSentenceLen =
    sents.length > 0 ? wordCount / sents.length : wordCount;
  const human = clamp(
    90 - Math.max(0, avgSentenceLen - 16) * 4 - longParas.length * 10 - aiTells.length * 10
  );
  // Promotional score: lower is better. Count promo signals.
  const promotional = clamp(promo.length * 22 + banned.length * 18);

  const overall = clamp(
    educational * 0.25 +
      trust * 0.2 +
      actionable * 0.2 +
      authentic * 0.2 +
      human * 0.15 -
      promotional * 0.2
  );

  return {
    scores: {
      educational,
      trust,
      actionable,
      authentic,
      human,
      promotional,
      overall,
    },
    warnings,
    wordCount,
    readTimeSeconds,
    paragraphs,
  };
}

export function pickCta(brand: BrandStyle, seed: number): string {
  const list = brand.allowedCtas;
  return list[seed % list.length];
}
