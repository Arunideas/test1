import type { BrandStyle } from "../types";

function hashOf(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) >>> 0;
  }
  return h;
}

export function keywordsFromTopic(topic: string): string[] {
  return topic
    .toLowerCase()
    .split(/\s+/)
    .filter((w) => w.length > 4)
    .slice(0, 3);
}

/**
 * Builds a small set of hashtags from topic keywords + the brand hashtag pool.
 * This is metadata generation (tagging), not content writing.
 */
export function pickHashtags(brand: BrandStyle, keywords: string[], seedText = ""): string[] {
  const tags = new Set<string>();
  for (const k of keywords) {
    const clean = k.replace(/[^a-z0-9]/gi, "");
    if (clean.length > 2) tags.add("#" + clean.charAt(0).toUpperCase() + clean.slice(1));
  }
  const pool = brand.hashtagPool;
  let i = hashOf(seedText || keywords.join(" "));
  while (tags.size < 4 && pool.length) {
    tags.add(pool[i % pool.length]);
    i++;
  }
  return [...tags].slice(0, 5);
}
