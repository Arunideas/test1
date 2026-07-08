import type { ImageTemplate } from "../types";

const NEGATIVE =
  "no beautiful AI people, no perfect smiling students, no corporate stock office, " +
  "no glossy render, no cinematic lighting, no lens flare, no text artifacts, " +
  "no watermark, no distorted hands, no plastic skin";

const STYLE =
  "documentary style, authentic, minimal, realistic smartphone photography, " +
  "natural lighting, Indian environment, slightly imperfect framing, no obvious AI artifacts";

export function buildImagePrompt(template: ImageTemplate, topic: string): string {
  return [
    `${template.scene}.`,
    `Context: ${topic}.`,
    STYLE + ".",
    `Avoid: ${NEGATIVE}.`,
  ].join(" ");
}

export function buildAltText(template: ImageTemplate, topic: string): string {
  return `${template.name} visual for a post about ${topic.toLowerCase()} — ${template.description}`;
}
