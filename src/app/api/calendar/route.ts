import { NextResponse } from "next/server";
import { listCalendar } from "@/lib/planning/service";

export const dynamic = "force-dynamic";

export async function GET() {
  const entries = await listCalendar();
  return NextResponse.json({ entries });
}
