import { newId, readDb, updateDb } from "../db";
import type {
  PublishJob,
  PublishLogLine,
  PublishMode,
  PublishStatus,
} from "../types";
import { linkedInStatus, publishToLinkedIn } from "./linkedin";

const TICK_MS = 10000;
const BASE_BACKOFF_MS = 4000;

function now(): number {
  return Date.now();
}
function iso(t = now()): string {
  return new Date(t).toISOString();
}
function line(message: string, level: PublishLogLine["level"] = "info"): PublishLogLine {
  return { at: iso(), message, level };
}

function composeText(body: string, hashtags: string[]): string {
  const tags = hashtags?.length ? "\n\n" + hashtags.join(" ") : "";
  return body + tags;
}

export interface SchedulePublishInput {
  postId: string;
  mode: PublishMode;
  scheduledAt?: string;
  visibility?: "PUBLIC" | "CONNECTIONS";
  calendarEntryId?: string;
}

export async function schedulePublish(
  input: SchedulePublishInput
): Promise<PublishJob | null> {
  const db = await readDb();
  const post = db.posts.find((p) => p.id === input.postId);
  if (!post) return null;

  const sim = linkedInStatus().simulated;
  let status: PublishStatus;
  switch (input.mode) {
    case "draft":
      status = "draft";
      break;
    case "approval":
      status = "pending_approval";
      break;
    case "scheduled":
      status = "scheduled";
      break;
    case "immediate":
    default:
      status = "queued";
      break;
  }

  const job: PublishJob = {
    id: newId("job"),
    postId: post.id,
    calendarEntryId: input.calendarEntryId ?? null,
    target: "linkedin",
    mode: input.mode,
    status,
    text: composeText(post.body, post.hashtags),
    hashtags: post.hashtags,
    imageId: post.imageId ?? null,
    visibility: input.visibility ?? "PUBLIC",
    scheduledAt: input.mode === "scheduled" ? input.scheduledAt ?? iso() : null,
    attempts: 0,
    maxAttempts: 4,
    nextAttemptAt: null,
    lastError: null,
    postUrl: null,
    simulated: sim,
    createdAt: iso(),
    updatedAt: iso(),
    approvedAt: null,
    publishedAt: null,
    log: [line(`Job created (${input.mode}${sim ? ", simulation" : ""})`)],
  };

  await updateDb((d) => {
    d.publishJobs.unshift(job);
  });

  ensureScheduler();
  if (job.status === "queued") await processDueJobs();
  return (await readDb()).publishJobs.find((j) => j.id === job.id) ?? job;
}

export async function approveJob(id: string): Promise<PublishJob | null> {
  const updated = await updateDb((d) => {
    const job = d.publishJobs.find((j) => j.id === id);
    if (!job) return null;
    if (job.status !== "pending_approval" && job.status !== "draft") return job;
    job.approvedAt = iso();
    if (job.scheduledAt && Date.parse(job.scheduledAt) > now()) {
      job.status = "scheduled";
      job.log.push(line("Approved — scheduled"));
    } else {
      job.status = "queued";
      job.log.push(line("Approved — queued for publishing"));
    }
    job.updatedAt = iso();
    return job;
  });
  ensureScheduler();
  await processDueJobs();
  return (await readDb()).publishJobs.find((j) => j.id === id) ?? updated;
}

export async function cancelJob(id: string): Promise<PublishJob | null> {
  return updateDb((d) => {
    const job = d.publishJobs.find((j) => j.id === id);
    if (!job) return null;
    if (job.status === "published") return job;
    job.status = "cancelled";
    job.updatedAt = iso();
    job.log.push(line("Cancelled"));
    return job;
  });
}

export async function retryJob(id: string): Promise<PublishJob | null> {
  const updated = await updateDb((d) => {
    const job = d.publishJobs.find((j) => j.id === id);
    if (!job) return null;
    if (job.status !== "failed" && job.status !== "cancelled") return job;
    job.status = "queued";
    job.nextAttemptAt = null;
    job.lastError = null;
    job.updatedAt = iso();
    job.log.push(line("Manual retry — re-queued"));
    return job;
  });
  ensureScheduler();
  await processDueJobs();
  return (await readDb()).publishJobs.find((j) => j.id === id) ?? updated;
}

function isDue(job: PublishJob, t: number): boolean {
  if (job.status === "queued") return true;
  if (job.status === "scheduled" && job.scheduledAt)
    return Date.parse(job.scheduledAt) <= t;
  if (
    job.status === "failed" &&
    job.nextAttemptAt &&
    job.attempts < job.maxAttempts
  )
    return Date.parse(job.nextAttemptAt) <= t;
  return false;
}

let processing = false;

export async function processDueJobs(): Promise<{ processed: number }> {
  if (processing) return { processed: 0 };
  processing = true;
  try {
    const t = now();
    // Atomically claim due jobs by marking them "publishing".
    const claimed = await updateDb((d) => {
      const due = d.publishJobs.filter((j) => isDue(j, t)).slice(0, 10);
      for (const j of due) {
        j.status = "publishing";
        j.attempts += 1;
        j.updatedAt = iso();
        j.log.push(line(`Publishing attempt ${j.attempts}/${j.maxAttempts}`));
      }
      return due.map((j) => {
        const image = d.images.find((img) => img.id === j.imageId);
        return {
          id: j.id,
          text: j.text,
          visibility: j.visibility,
          imageData: image?.svg ?? null,
          imageAltText: image?.altText ?? null,
        };
      });
    });

    for (const c of claimed) {
      const result = await publishToLinkedIn({
        text: c.text,
        visibility: c.visibility,
        image: c.imageData
          ? {
              data: c.imageData,
              altText: c.imageAltText,
            }
          : null,
      });
      await updateDb((d) => {
        const job = d.publishJobs.find((j) => j.id === c.id);
        if (!job) return;
        if (result.ok) {
          job.status = "published";
          job.postUrl = result.postUrl ?? null;
          job.publishedAt = iso();
          job.lastError = null;
          job.nextAttemptAt = null;
          job.simulated = result.simulated;
          job.log.push(
            line(
              result.simulated
                ? `Published (simulated${result.imageAttached ? " with image" : ""}): ${
                    job.postUrl
                  }`
                : `Published${result.imageAttached ? " with image" : ""}: ${job.postUrl}`,
              "success"
            )
          );
          // propagate to related entities
          const post = d.posts.find((p) => p.id === job.postId);
          if (post) {
            post.status = "published";
            if (post.topicId) {
              const topic = d.topics.find((x) => x.id === post.topicId);
              if (topic) {
                topic.lastPublishedAt = iso();
                topic.status = "published";
              }
            }
          }
          if (job.calendarEntryId) {
            const entry = d.calendar.find((e) => e.id === job.calendarEntryId);
            if (entry) entry.status = "published";
          }
        } else {
          job.lastError = result.error ?? "Unknown error";
          if (job.attempts < job.maxAttempts) {
            const delay = BASE_BACKOFF_MS * Math.pow(2, job.attempts - 1);
            job.status = "failed";
            job.nextAttemptAt = iso(now() + delay);
            job.log.push(
              line(`Failed: ${job.lastError}. Retrying in ${Math.round(delay / 1000)}s`, "error")
            );
          } else {
            job.status = "failed";
            job.nextAttemptAt = null;
            job.log.push(line(`Failed permanently: ${job.lastError}`, "error"));
          }
        }
        job.updatedAt = iso();
      });
    }

    return { processed: claimed.length };
  } finally {
    processing = false;
  }
}

export async function listJobs(): Promise<PublishJob[]> {
  const db = await readDb();
  return [...db.publishJobs].sort(
    (a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt)
  );
}

export async function getPublishStatus() {
  const db = await readDb();
  const counts: Record<string, number> = {};
  for (const j of db.publishJobs) counts[j.status] = (counts[j.status] ?? 0) + 1;
  return { linkedin: linkedInStatus(), counts, total: db.publishJobs.length };
}

/**
 * Auto-publish: turn generated/approved calendar entries into scheduled LinkedIn jobs.
 * Entries are scheduled at their calendar date and the given time-of-day.
 */
export async function autoScheduleCalendar(timeOfDay = "09:00") {
  const db = await readDb();
  const sim = linkedInStatus().simulated;
  const existing = new Set(
    db.publishJobs
      .filter((j) => j.calendarEntryId && j.status !== "cancelled")
      .map((j) => j.calendarEntryId)
  );
  const created: PublishJob[] = [];

  for (const entry of db.calendar) {
    if (!entry.postId) continue;
    if (entry.status !== "approved" && entry.status !== "generated") continue;
    if (existing.has(entry.id)) continue;
    const post = db.posts.find((p) => p.id === entry.postId);
    if (!post) continue;

    const job: PublishJob = {
      id: newId("job"),
      postId: post.id,
      calendarEntryId: entry.id,
      target: "linkedin",
      mode: "scheduled",
      status: "scheduled",
      text: composeText(post.body, post.hashtags),
      hashtags: post.hashtags,
      imageId: post.imageId ?? null,
      visibility: "PUBLIC",
      scheduledAt: new Date(`${entry.date}T${timeOfDay}:00Z`).toISOString(),
      attempts: 0,
      maxAttempts: 4,
      nextAttemptAt: null,
      lastError: null,
      postUrl: null,
      simulated: sim,
      createdAt: iso(),
      updatedAt: iso(),
      approvedAt: iso(),
      publishedAt: null,
      log: [line(`Auto-scheduled from calendar for ${entry.date} ${timeOfDay}`)],
    };
    created.push(job);
  }

  await updateDb((d) => {
    d.publishJobs.unshift(...created);
  });
  ensureScheduler();
  await processDueJobs();
  return { created: created.length };
}

// ---- Background scheduler ----
type GlobalWithTimer = typeof globalThis & { __woiPublishTimer?: NodeJS.Timeout };

export function ensureScheduler() {
  const g = globalThis as GlobalWithTimer;
  if (g.__woiPublishTimer) return;
  g.__woiPublishTimer = setInterval(() => {
    processDueJobs().catch(() => undefined);
  }, TICK_MS);
  // don't keep the event loop alive solely for this timer
  if (typeof g.__woiPublishTimer.unref === "function") g.__woiPublishTimer.unref();
}
