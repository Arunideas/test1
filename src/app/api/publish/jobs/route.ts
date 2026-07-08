import { NextResponse } from "next/server";
import { ensureScheduler, listJobs, processDueJobs } from "@/lib/publishing/service";

export const dynamic = "force-dynamic";

export async function GET() {
  ensureScheduler();
  // opportunistic tick so due jobs progress even without the background timer
  await processDueJobs();
  const jobs = await listJobs();
  return NextResponse.json({ jobs });
}
