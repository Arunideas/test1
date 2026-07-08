import { readDb } from "../db";
import { buildPlan, generateForEntry } from "../planning/service";
import { ymd } from "../planning/planner";
import { autoScheduleCalendar, processDueJobs } from "./service";

export interface DailyPipelineOptions {
  planIfEmpty?: boolean; // build a calendar if none exists (default true)
  days?: number; // calendar length when planning (default 90)
  horizonDays?: number; // also generate entries due within N days ahead (default 0 = today + overdue)
  timeOfDay?: string; // schedule time for auto-scheduled posts (default 09:00)
  generate?: boolean; // generate due posts (default true)
}

export interface DailyPipelineResult {
  planned: number;
  generated: number;
  scheduled: number;
  published: number;
  today: string;
}

function addDaysYmd(d: string, n: number): string {
  const dt = new Date(d + "T00:00:00Z");
  dt.setUTCDate(dt.getUTCDate() + n);
  return dt.toISOString().slice(0, 10);
}

/**
 * One call that a scheduler (cron) can hit to run the whole daily loop:
 *  1. ensure a content calendar exists,
 *  2. generate posts + images for entries that are due and not yet generated,
 *  3. auto-schedule approved/generated entries as LinkedIn jobs,
 *  4. publish any jobs that are now due.
 */
export async function runDailyPipeline(
  opts: DailyPipelineOptions = {}
): Promise<DailyPipelineResult> {
  const result: DailyPipelineResult = {
    planned: 0,
    generated: 0,
    scheduled: 0,
    published: 0,
    today: ymd(new Date()),
  };

  let db = await readDb();

  if (!db.calendar.length && opts.planIfEmpty !== false) {
    const plan = await buildPlan({ days: opts.days ?? 90 });
    result.planned = plan.summary.scheduled;
    db = await readDb();
  }

  if (opts.generate !== false) {
    const cutoff = addDaysYmd(result.today, opts.horizonDays ?? 0);
    const due = db.calendar.filter(
      (e) =>
        e.date <= cutoff &&
        !e.postId &&
        e.status !== "skipped" &&
        e.status !== "rejected" &&
        e.status !== "published"
    );
    for (const entry of due) {
      const res = await generateForEntry(entry.id);
      if (res?.post) result.generated += 1;
    }
  }

  const publishedBefore = (await readDb()).publishJobs.filter(
    (j) => j.status === "published"
  ).length;

  const sched = await autoScheduleCalendar(opts.timeOfDay ?? "09:00");
  result.scheduled = sched.created;

  await processDueJobs();

  const publishedAfter = (await readDb()).publishJobs.filter(
    (j) => j.status === "published"
  ).length;
  result.published = Math.max(0, publishedAfter - publishedBefore);

  return result;
}
