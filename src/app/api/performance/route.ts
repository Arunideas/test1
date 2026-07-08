import { NextResponse } from "next/server";
import { recordPerformance } from "@/lib/planning/service";
import type { PerformanceRecord } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const body = (await req.json()) as {
    calendarEntryId?: string;
    postId?: string;
    metrics?: Partial<PerformanceRecord["metrics"]>;
  };
  const m = body.metrics ?? {};
  const metrics: PerformanceRecord["metrics"] = {
    views: m.views ?? 0,
    likes: m.likes ?? 0,
    comments: m.comments ?? 0,
    shares: m.shares ?? 0,
    impressions: m.impressions ?? m.views ?? 0,
    ctr: m.ctr ?? 0,
    engagementRate: m.engagementRate ?? 0,
  };
  const record = await recordPerformance({
    calendarEntryId: body.calendarEntryId,
    postId: body.postId,
    metrics,
  });
  return NextResponse.json({ record });
}
