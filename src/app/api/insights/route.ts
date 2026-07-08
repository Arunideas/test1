import { NextResponse } from "next/server";
import { getInsights } from "@/lib/planning/service";

export const dynamic = "force-dynamic";

export async function GET() {
  const insights = await getInsights();
  return NextResponse.json(insights);
}
