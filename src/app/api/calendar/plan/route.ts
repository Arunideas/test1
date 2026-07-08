import { NextResponse } from "next/server";
import { buildPlan } from "@/lib/planning/service";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  try {
    const body = (await req.json().catch(() => ({}))) as {
      days?: number;
      startDate?: string;
    };
    const result = await buildPlan(body);
    return NextResponse.json(result);
  } catch (err) {
    console.error("plan error", err);
    return NextResponse.json({ error: "Failed to build plan" }, { status: 500 });
  }
}
