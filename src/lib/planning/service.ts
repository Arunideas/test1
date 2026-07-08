import { newId, readDb, updateDb } from "../db";
import { CONTENT_TYPES } from "../content/contentTypes";
import { generatePost } from "../service";
import type {
  CalendarEntry,
  CalendarStatus,
  PerformanceRecord,
} from "../types";
import {
  categoryBalance,
  hasPostedBefore,
  nextTopic,
  performanceScore,
  planCalendar,
  trendingTopics,
} from "./planner";
import { bestMatches } from "./similarity";

function audienceMap(): Record<string, string> {
  const map: Record<string, string> = {};
  for (const ct of CONTENT_TYPES) map[ct.id] = ct.defaultAudience;
  return map;
}

export interface BuildPlanInput {
  days?: number;
  startDate?: string;
}

export async function buildPlan(input: BuildPlanInput) {
  const db = await readDb();
  const days = Math.max(1, Math.min(365, input.days ?? 90));
  const result = planCalendar(db, audienceMap(), {
    days,
    startDate: input.startDate,
  });

  // Preserve generated/published entries (with posts) that fall on the same date.
  const preserved = new Map<string, CalendarEntry>();
  for (const e of db.calendar) {
    if ((e.status === "generated" || e.status === "published") && e.postId) {
      preserved.set(e.date, e);
    }
  }
  const entries = result.entries.map((e) => preserved.get(e.date) ?? e);

  await updateDb((d) => {
    d.calendar = entries;
  });

  return { ...result, entries };
}

export async function listCalendar() {
  const db = await readDb();
  const entries = [...db.calendar].sort((a, b) => a.date.localeCompare(b.date));
  return entries.map((e) => ({
    ...e,
    categoryName: db.categories.find((c) => c.id === e.categoryId)?.name ?? e.categoryId,
    contentTypeName:
      CONTENT_TYPES.find((c) => c.id === e.contentTypeId)?.name ?? e.contentTypeId,
  }));
}

export async function updateEntry(
  id: string,
  patch: { status?: CalendarStatus; note?: string; topicId?: string; approvedBy?: string }
) {
  const db = await readDb();
  return updateDb((d) => {
    const entry = d.calendar.find((c) => c.id === id);
    if (!entry) return null;
    if (patch.status) {
      entry.status = patch.status;
      if (patch.status === "approved") {
        entry.approvedBy = patch.approvedBy || "admin";
        entry.approvedAt = new Date().toISOString();
      }
    }
    if (typeof patch.note === "string") entry.note = patch.note;
    if (patch.topicId) {
      const t = db.topics.find((x) => x.id === patch.topicId);
      if (t) {
        entry.topicId = t.id;
        entry.topicText = t.topic;
        entry.categoryId = t.categoryId;
      }
    }
    return entry;
  });
}

export async function generateForEntry(id: string) {
  const db = await readDb();
  const entry = db.calendar.find((c) => c.id === id);
  if (!entry) return null;

  const result = await generatePost({
    contentTypeId: entry.contentTypeId,
    topicId: entry.topicId,
    categoryId: entry.categoryId,
    audience: entry.audience,
  });

  const updated = await updateDb((d) => {
    const e = d.calendar.find((c) => c.id === id);
    if (!e) return null;
    e.postId = result.post.id;
    if (e.status === "planned" || e.status === "approved") {
      e.status = "generated";
    }
    return e;
  });

  return { entry: updated, post: result.post, image: result.image };
}

export async function getQueue() {
  const db = await readDb();
  return [...db.calendar]
    .filter((c) => c.status === "approved" || c.status === "generated")
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((e) => ({
      ...e,
      categoryName: db.categories.find((c) => c.id === e.categoryId)?.name ?? e.categoryId,
    }));
}

export interface RecordPerformanceInput {
  calendarEntryId?: string;
  postId?: string;
  topicId?: string;
  categoryId?: string;
  metrics: PerformanceRecord["metrics"];
  date?: string;
}

export async function recordPerformance(input: RecordPerformanceInput) {
  const db = await readDb();
  let topicId = input.topicId;
  let categoryId = input.categoryId;
  if (input.calendarEntryId) {
    const e = db.calendar.find((c) => c.id === input.calendarEntryId);
    if (e) {
      topicId = topicId || e.topicId;
      categoryId = categoryId || e.categoryId;
    }
  }
  const score = performanceScore(input.metrics);
  const record: PerformanceRecord = {
    id: newId("perf"),
    calendarEntryId: input.calendarEntryId ?? null,
    postId: input.postId ?? null,
    topicId: topicId || "",
    categoryId: categoryId || "",
    date: input.date || new Date().toISOString().slice(0, 10),
    metrics: input.metrics,
    score,
    createdAt: new Date().toISOString(),
  };

  return updateDb((d) => {
    d.performance.push(record);
    if (input.calendarEntryId) {
      const e = d.calendar.find((c) => c.id === input.calendarEntryId);
      if (e) {
        e.status = "published";
      }
    }
    if (topicId) {
      const t = d.topics.find((x) => x.id === topicId);
      if (t) {
        // blend past performance toward the observed score
        t.performanceScore = Math.round(t.performanceScore * 0.6 + score * 0.4);
        t.lastPublishedAt = record.date;
        t.status = "published";
      }
    }
    return record;
  });
}

export async function getInsights() {
  const db = await readDb();
  const balance = categoryBalance(db);
  const next = nextTopic(db);
  const trending = trendingTopics(db.topics, 6);

  // Duplicate alerts across the current calendar.
  const alerts: { a: string; b: string; score: number; dateA: string; dateB: string }[] = [];
  const cal = db.calendar;
  for (let i = 0; i < cal.length; i++) {
    const matches = bestMatches(
      cal[i].topicText,
      cal.slice(i + 1).map((c) => ({ id: c.id, topic: c.topicText, date: c.date })),
      2
    );
    for (const m of matches) {
      if (m.score >= db.config.duplicateThreshold) {
        alerts.push({
          a: cal[i].topicText,
          b: m.topic,
          score: m.score,
          dateA: cal[i].date,
          dateB: m.date ?? "",
        });
      }
    }
  }

  return {
    config: db.config,
    next: next
      ? {
          topic: next.topic.topic,
          topicId: next.topic.id,
          categoryId: next.topic.categoryId,
          score: next.score,
        }
      : null,
    underrepresented: balance.underrepresented.slice(0, 5).map((r) => ({
      ...r,
      categoryName: db.categories.find((c) => c.id === r.categoryId)?.name ?? r.categoryId,
    })),
    categoryBalance: balance.rows.map((r) => ({
      ...r,
      categoryName: db.categories.find((c) => c.id === r.categoryId)?.name ?? r.categoryId,
    })),
    trending: trending.map((t) => ({
      topic: t.topic,
      topicId: t.id,
      trendScore: t.trendScore,
      categoryName: db.categories.find((c) => c.id === t.categoryId)?.name ?? t.categoryId,
    })),
    duplicateAlerts: alerts,
  };
}

export async function checkDuplicate(topicText: string) {
  const db = await readDb();
  return hasPostedBefore(topicText, db);
}
