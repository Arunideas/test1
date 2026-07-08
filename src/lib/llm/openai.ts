import type { BrandStyle } from "../types";

const OPENAI_BASE = process.env.OPENAI_BASE_URL || "https://api.openai.com/v1";
const TEXT_MODEL = process.env.OPENAI_TEXT_MODEL || "gpt-4o-mini";
const IMAGE_MODEL = process.env.OPENAI_IMAGE_MODEL || "gpt-image-1";

export function hasOpenAI(): boolean {
  return Boolean(process.env.OPENAI_API_KEY);
}

function buildSystemPrompt(brand: BrandStyle, systemHint: string): string {
  return [
    `You write LinkedIn posts for ${brand.brandName}.`,
    `Primary positioning: ${brand.positioningPrimary}`,
    `Secondary: ${brand.positioningSecondary}`,
    `Tone: ${brand.tone.join(", ")}. Never: ${brand.avoidTone.join(", ")}.`,
    `Structure the post: ${brand.structure.join(" -> ")}.`,
    `Rules: short sentences; one idea per paragraph; max ${brand.maxLinesPerParagraph} lines per paragraph.`,
    `Never sound like AI, motivational, or an advertisement.`,
    `Never invent named people (no ${brand.bannedNames.join(
      ", "
    )}). Use "a final year student", "a recruiter", or real platform patterns.`,
    `Never use these phrases: ${brand.bannedPhrases.slice(0, 12).join(", ")}.`,
    `End with a soft question CTA like: ${brand.allowedCtas
      .slice(0, 3)
      .map((c) => `"${c}"`)
      .join(", ")}. Never "Register Now".`,
    `Keep it valuable even if the brand name is removed. Under 180 words.`,
    systemHint,
    `Return ONLY the post text. No preamble, no markdown headers.`,
  ].join("\n");
}

export async function generatePostWithLLM(params: {
  brand: BrandStyle;
  systemHint: string;
  topic: string;
  audience: string;
  extra?: string;
}): Promise<string | null> {
  if (!hasOpenAI()) return null;
  try {
    const res = await fetch(`${OPENAI_BASE}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
      },
      body: JSON.stringify({
        model: TEXT_MODEL,
        temperature: 0.7,
        messages: [
          { role: "system", content: buildSystemPrompt(params.brand, params.systemHint) },
          {
            role: "user",
            content: `Topic: ${params.topic}\nAudience: ${params.audience}${
              params.extra ? `\nExtra context: ${params.extra}` : ""
            }`,
          },
        ],
      }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    const text: string | undefined = data?.choices?.[0]?.message?.content;
    return text?.trim() || null;
  } catch {
    return null;
  }
}

export async function generateTextWithLLM(
  system: string,
  user: string,
  temperature = 0.7
): Promise<string | null> {
  if (!hasOpenAI()) return null;
  try {
    const res = await fetch(`${OPENAI_BASE}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
      },
      body: JSON.stringify({
        model: TEXT_MODEL,
        temperature,
        messages: [
          { role: "system", content: system },
          { role: "user", content: user },
        ],
      }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    const text: string | undefined = data?.choices?.[0]?.message?.content;
    return text?.trim() || null;
  } catch {
    return null;
  }
}

export async function generateImageWithOpenAI(prompt: string): Promise<string | null> {
  if (!hasOpenAI()) return null;
  try {
    const res = await fetch(`${OPENAI_BASE}/images/generations`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
      },
      body: JSON.stringify({
        model: IMAGE_MODEL,
        prompt,
        size: "1024x1024",
        n: 1,
      }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    const b64: string | undefined = data?.data?.[0]?.b64_json;
    if (b64) return `data:image/png;base64,${b64}`;
    const url: string | undefined = data?.data?.[0]?.url;
    return url ?? null;
  } catch {
    return null;
  }
}
