import { NextResponse } from "next/server";
import { ensureScheduler, getPublishStatus } from "@/lib/publishing/service";

export const dynamic = "force-dynamic";

export async function GET() {
  ensureScheduler();
  const status = await getPublishStatus();
  return NextResponse.json(status);
}
