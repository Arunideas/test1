import type {
  CalendarEntry,
  Category,
  Database,
  PerformanceRecord,
  PlatformConfig,
  Topic,
  WeekdaySlot,
} from "../types";
import { bestMatches, similarity } from "./similarity";

export function ymd(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function addDays(d: Date, n: number): Date {
  const copy = new Date(d);
  copy.setUTCDate(copy.getUTCDate() + n);
  return copy;
}

function daysBetween(a: string, b: string): number {
  return Math.abs(
    Math.round((Date.parse(a) - Date.parse(b)) / (1000 * 60 * 60 * 24))
  );
}

/**
 * Topic score (0-100) used to decide "which topic should be next".
 * Blends editorial priority, trend, popularity, past performance, and freshness
 * (recently used topics are penalised so we rotate).
 */
export function topicScore(
  topic: Topic,
  config: PlatformConfig,
  now = new Date()
): number {
  const base =
    topic.priority * 6 + // 12..30
    topic.trendScore * 0.3 + // 0..30
    topic.popularity * 0.15 + // 0..15
    topic.performanceScore * 0.15; // 0..15

  let freshnessPenalty = 0;
  const last = topic.lastPublishedAt || topic.lastGeneratedAt;
  if (last) {
    const age = daysBetween(ymd(now), last);
    if (age < config.rotationWindowDays) {
      // full penalty right after use, decaying to 0 at the window edge
      freshnessPenalty = 40 * (1 - age / config.rotationWindowDays);
    }
  }
  return Math.max(0, Math.min(100, Math.round(base - freshnessPenalty)));
}

/** "Which topics are trending?" */
export function trendingTopics(topics: Topic[], limit = 6): Topic[] {
  return [...topics]
    .sort((a, b) => b.trendScore - a.trendScore || b.popularity - a.popularity)
    .slice(0, limit);
}

/** "Have we posted this before?" — checks published/scheduled history for near-duplicates. */
export function hasPostedBefore(
  topicText: string,
  db: Database,
  withinDays?: number
) {
  const now = ymd(new Date());
  const history: { id: string; topic: string; date?: string | null }[] = [];
  for (const p of db.posts) {
    history.push({ id: p.id, topic: p.topic, date: p.createdAt.slice(0, 10) });
  }
  for (const c of db.calendar) {
    history.push({ id: c.id, topic: c.topicText, date: c.date });
  }
  let matches = bestMatches(topicText, history, 5);
  if (withinDays) {
    matches = matches.filter(
      (m) => !m.date || daysBetween(now, m.date) <= withinDays
    );
  }
  const threshold = db.config.duplicateThreshold;
  const dup = matches.filter((m) => m.score >= threshold);
  return {
    posted: dup.length > 0,
    threshold,
    matches,
    duplicates: dup,
  };
}

/**
 * "Which category is underrepresented?" — compares each category's recent share
 * of the calendar to an even target.
 */
export function categoryBalance(db: Database, lookbackDays = 90) {
  const now = ymd(new Date());
  const counts = new Map<string, number>();
  const relevant = new Set<string>();
  for (const slot of db.config.weekdayPlan) {
    for (const c of slot.categoryIds) relevant.add(c);
  }
  for (const c of relevant) counts.set(c, 0);

  for (const entry of db.calendar) {
    if (daysBetween(now, entry.date) > lookbackDays) continue;
    if (entry.status === "rejected" || entry.status === "skipped") continue;
    counts.set(entry.categoryId, (counts.get(entry.categoryId) ?? 0) + 1);
  }

  const total = [...counts.values()].reduce((a, b) => a + b, 0);
  const target = total / Math.max(1, counts.size);
  const rows = [...counts.entries()]
    .map(([categoryId, count]) => ({
      categoryId,
      count,
      target: Number(target.toFixed(1)),
      deficit: Number((target - count).toFixed(1)),
    }))
    .sort((a, b) => b.deficit - a.deficit);

  return { total, rows, underrepresented: rows.filter((r) => r.deficit > 0) };
}

interface PickState {
  usedTopicIds: Set<string>;
  scheduledTexts: { id: string; topic: string; date?: string | null }[];
  slotCategoryCounts: Map<string, Map<string, number>>; // weekday -> category -> count
}

function chooseCategory(slot: WeekdaySlot, state: PickState): string[] {
  const perCat = state.slotCategoryCounts.get(String(slot.weekday))!;
  // order categories by least used so far (balancing within the slot)
  return [...slot.categoryIds].sort(
    (a, b) => (perCat.get(a) ?? 0) - (perCat.get(b) ?? 0)
  );
}

function pickTopicForCategory(
  categoryId: string,
  topics: Topic[],
  state: PickState,
  config: PlatformConfig,
  now: Date
): Topic | null {
  const candidates = topics
    .filter((t) => t.categoryId === categoryId && !state.usedTopicIds.has(t.id))
    .map((t) => ({ t, score: topicScore(t, config, now) }))
    .sort((a, b) => b.score - a.score);

  for (const { t } of candidates) {
    const dup = state.scheduledTexts.reduce(
      (max, s) => Math.max(max, similarity(t.topic, s.topic)),
      0
    );
    if (dup < config.duplicateThreshold) return t;
  }
  return null;
}

export interface PlanOptions {
  days: number;
  startDate?: string; // YYYY-MM-DD
  audienceByType?: Record<string, string>;
}

export interface PlanResult {
  entries: CalendarEntry[];
  summary: {
    days: number;
    scheduled: number;
    uniqueTopics: number;
    duplicateTopics: number;
    maxSimilarity: number;
    categoriesUsed: number;
  };
}

/**
 * Build a content calendar for `days` days with no duplicate topics,
 * rotating topics and balancing categories per weekday theme.
 */
export function planCalendar(
  db: Database,
  contentTypeAudience: Record<string, string>,
  opts: PlanOptions
): PlanResult {
  const now = new Date();
  const start = opts.startDate ? new Date(opts.startDate + "T00:00:00Z") : now;
  const config = db.config;

  const state: PickState = {
    usedTopicIds: new Set(),
    scheduledTexts: [],
    slotCategoryCounts: new Map(),
  };
  for (const slot of config.weekdayPlan) {
    state.slotCategoryCounts.set(
      String(slot.weekday),
      new Map(slot.categoryIds.map((c) => [c, 0]))
    );
  }

  // Seed history with already-published posts so we don't repeat recent ones.
  for (const p of db.posts) {
    state.scheduledTexts.push({
      id: p.id,
      topic: p.topic,
      date: p.createdAt.slice(0, 10),
    });
    if (p.topicId) state.usedTopicIds.add(p.topicId);
  }

  const entries: CalendarEntry[] = [];
  let maxSim = 0;

  for (let i = 0; i < opts.days; i++) {
    const date = addDays(start, i);
    const weekday = date.getUTCDay();
    const slot = config.weekdayPlan.find((s) => s.weekday === weekday)!;
    const perCat = state.slotCategoryCounts.get(String(weekday))!;

    // try the balanced category order, then fall back to any slot category,
    // then any topic for the same content type.
    let chosen: { topic: Topic; categoryId: string } | null = null;
    for (const cat of chooseCategory(slot, state)) {
      const t = pickTopicForCategory(cat, db.topics, state, config, now);
      if (t) {
        chosen = { topic: t, categoryId: cat };
        break;
      }
    }
    if (!chosen) {
      // fallback: any unused topic anywhere, preferring low duplicate similarity
      const t = pickTopicForCategory(
        "",
        db.topics.filter((x) => !state.usedTopicIds.has(x.id)),
        { ...state, usedTopicIds: new Set() },
        config,
        now
      );
      if (t) chosen = { topic: t, categoryId: t.categoryId };
    }
    if (!chosen) continue; // no topics left at all

    const dup = state.scheduledTexts.reduce(
      (m, s) => Math.max(m, similarity(chosen!.topic.topic, s.topic)),
      0
    );
    maxSim = Math.max(maxSim, dup);

    const entry: CalendarEntry = {
      id: `cal_${ymd(date)}_${weekday}`,
      date: ymd(date),
      slot: slot.label,
      contentTypeId: slot.contentTypeId,
      categoryId: chosen.categoryId,
      topicId: chosen.topic.id,
      topicText: chosen.topic.topic,
      audience: (contentTypeAudience[slot.contentTypeId] as CalendarEntry["audience"]) || "students",
      status: "planned",
      duplicateScore: dup,
      topicScore: topicScore(chosen.topic, config, now),
      postId: null,
      approvedBy: null,
      approvedAt: null,
      createdAt: new Date().toISOString(),
    };
    entries.push(entry);

    state.usedTopicIds.add(chosen.topic.id);
    state.scheduledTexts.push({
      id: entry.id,
      topic: entry.topicText,
      date: entry.date,
    });
    perCat.set(chosen.categoryId, (perCat.get(chosen.categoryId) ?? 0) + 1);
  }

  const topicTexts = entries.map((e) => e.topicText.toLowerCase());
  const uniqueTopics = new Set(topicTexts).size;
  const cats = new Set(entries.map((e) => e.categoryId));

  return {
    entries,
    summary: {
      days: opts.days,
      scheduled: entries.length,
      uniqueTopics,
      duplicateTopics: entries.length - uniqueTopics,
      maxSimilarity: Number(maxSim.toFixed(3)),
      categoriesUsed: cats.size,
    },
  };
}

/** "Which topic should be next?" — best-scoring unused/fresh topic. */
export function nextTopic(db: Database) {
  const scheduledTopicIds = new Set(
    db.calendar
      .filter((c) => c.status !== "rejected" && c.status !== "skipped")
      .map((c) => c.topicId)
  );
  const now = new Date();
  const ranked = db.topics
    .map((t) => ({
      topic: t,
      score: topicScore(t, db.config, now),
      scheduled: scheduledTopicIds.has(t.id),
    }))
    .sort((a, b) => {
      if (a.scheduled !== b.scheduled) return a.scheduled ? 1 : -1;
      return b.score - a.score;
    });
  return ranked[0] ?? null;
}

/** Blended performance score (0-100) from raw metrics. */
export function performanceScore(m: PerformanceRecord["metrics"]): number {
  const er = m.engagementRate * 100; // 0..~10 typically
  const ctr = m.ctr * 100;
  const reach = Math.min(100, Math.log10(Math.max(1, m.impressions)) * 20);
  return Math.round(Math.min(100, er * 4 + ctr * 2 + reach * 0.4));
}

export function categoryName(categories: Category[], id: string): string {
  return categories.find((c) => c.id === id)?.name ?? id;
}
