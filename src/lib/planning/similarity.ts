// Lightweight, dependency-free text similarity for topic duplicate detection.

const STOPWORDS = new Set([
  "the","a","an","to","of","for","and","or","in","on","with","your","you","how",
  "why","what","when","is","are","that","this","it","not","without","before",
  "into","from","at","as","but","if","do","does","most","one","two","three",
  "you're","we","our","us","can","will","should","which","who","them","they",
]);

function stemLite(w: string): string {
  return w
    .replace(/(ing|ed|ers|er|ies|ial|ions|ion|ments|ment|ness|s)$/i, "")
    .replace(/y$/i, "i");
}

export function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((w) => w.length > 2 && !STOPWORDS.has(w))
    .map(stemLite);
}

function jaccard(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 && b.size === 0) return 0;
  let inter = 0;
  for (const x of a) if (b.has(x)) inter++;
  const union = a.size + b.size - inter;
  return union === 0 ? 0 : inter / union;
}

function bigrams(tokens: string[]): Set<string> {
  const out = new Set<string>();
  for (let i = 0; i < tokens.length - 1; i++) {
    out.add(tokens[i] + " " + tokens[i + 1]);
  }
  return out;
}

/**
 * Similarity in [0, 1]. Blends unigram Jaccard (topic overlap) with bigram
 * Jaccard (phrase order), which catches near-duplicate headlines well.
 */
export function similarity(a: string, b: string): number {
  const ta = tokenize(a);
  const tb = tokenize(b);
  const uni = jaccard(new Set(ta), new Set(tb));
  const bi = jaccard(bigrams(ta), bigrams(tb));
  return Number((uni * 0.65 + bi * 0.35).toFixed(3));
}

export interface SimilarItem {
  id: string;
  topic: string;
  date?: string | null;
}

export interface Match {
  id: string;
  topic: string;
  date?: string | null;
  score: number;
}

export function bestMatches(
  topic: string,
  others: SimilarItem[],
  limit = 3
): Match[] {
  return others
    .map((o) => ({ ...o, score: similarity(topic, o.topic) }))
    .filter((o) => o.score > 0)
    .sort((x, y) => y.score - x.score)
    .slice(0, limit);
}
