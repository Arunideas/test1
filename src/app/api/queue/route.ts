import { NextResponse } from "next/server";
import { getQueue } from "@/lib/planning/service";

export const dynamic = "force-dynamic";

export async function GET() {
  const queue = await getQueue();
  return NextResponse.json({ queue });
}
