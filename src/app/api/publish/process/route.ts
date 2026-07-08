import { NextResponse } from "next/server";
import { ensureScheduler, processDueJobs } from "@/lib/publishing/service";

export const dynamic = "force-dynamic";

// Call this from an external cron (e.g. every minute) to publish due jobs,
// in addition to the in-process background scheduler.
export async function POST() {
  ensureScheduler();
  const result = await processDueJobs();
  return NextResponse.json(result);
}

export const GET = POST;
