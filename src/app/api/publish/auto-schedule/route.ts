import { NextResponse } from "next/server";
import { autoScheduleCalendar } from "@/lib/publishing/service";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const body = (await req.json().catch(() => ({}))) as { timeOfDay?: string };
  const result = await autoScheduleCalendar(body.timeOfDay || "09:00");
  return NextResponse.json(result);
}
